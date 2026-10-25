"""Baseline behavior and leakage boundaries on synthetic timing-only samples."""

import asyncio
from collections.abc import Iterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.baseline import (
    Recording,
    calibrate_threshold,
    extract_features,
    fit_baselines,
    score_sample,
)
from app.database import Base, BaselineArtifact, get_db
from app.main import app
from app.schemas import CHALLENGE_LENGTH, TimingSequence


def sequence(hold: float, gap: float) -> TimingSequence:
    n = CHALLENGE_LENGTH
    return TimingSequence(
        hold_ms=[hold] * n,
        down_down_ms=[hold + gap] * (n - 1),
        flight_ms=[gap] * (n - 1),
        long_pauses=[gap >= 750] * (n - 1),
        total_ms=(hold + gap) * (n - 1) + hold,
    )


def recordings() -> list[Recording]:
    return [
        Recording(
            sample_id=profile_id * 100 + i,
            profile_id=profile_id,
            session_id=f"session-{profile_id}-{i // 3}",
            timing_sequence=sequence(
                80 + profile_id * 170 + i, 65 + profile_id * 150 + i
            ),
        )
        for profile_id in (1, 2)
        for i in range(6)
    ]


def test_features_and_training_split_are_deterministic() -> None:
    items = recordings()
    matrix = extract_features(items[0].timing_sequence)
    assert matrix == extract_features(items[0].timing_sequence.model_dump())
    assert len(matrix) == CHALLENGE_LENGTH
    assert matrix[0] == (250.0, 465.0, 0.0)
    assert matrix[-1] == (250.0, 0.0, 0.0)

    models = fit_baselines(items)
    target = models[1]
    assert set(target.train_ids).isdisjoint(target.validation_ids)
    assert target.session_disjoint
    assert len(target.train_ids) == 3
    assert len(target.validation_ids) == 3
    assert target.calibration.genuine_count == 3
    assert target.calibration.impostor_count == 3
    assert target == fit_baselines(list(reversed(items)))[1]

    genuine_score, _, genuine_accepted = score_sample(target, sequence(255, 220))
    impostor_score, _, impostor_accepted = score_sample(target, sequence(425, 370))
    assert genuine_score > impostor_score
    assert genuine_accepted
    assert not impostor_accepted


def test_validation_data_does_not_fit_scaler() -> None:
    items = recordings()
    original = fit_baselines(items)[1]
    changed = [
        Recording(item.sample_id, item.profile_id, item.session_id, sequence(1000, 900))
        if item.sample_id % 100 >= 3
        else item
        for item in items
    ]
    recalibrated = fit_baselines(changed)[1]
    assert original.scaler == recalibrated.scaler
    assert original.prototype == recalibrated.prototype
    assert original.threshold_distance != recalibrated.threshold_distance


def test_validation_metrics_and_invalid_values() -> None:
    threshold, rates = calibrate_threshold([0.1, 0.2], [0.8, 0.9])
    assert 0.2 < threshold < 0.8
    assert rates.false_acceptance_rate == rates.false_rejection_rate == 0
    tied_threshold, tied_rates = calibrate_threshold([0.0], [0.0])
    assert tied_threshold == 0
    assert tied_rates.false_acceptance_rate == 0
    assert tied_rates.false_rejection_rate == 1
    with pytest.raises(ValueError):
        extract_features(
            {
                **sequence(80, 70).model_dump(),
                "hold_ms": [float("nan")] * CHALLENGE_LENGTH,
            }
        )
    with pytest.raises(ValueError):
        calibrate_threshold([float("inf")], [1.0])


@pytest.fixture
def client_db(tmp_path: Path) -> Iterator[tuple[AsyncClient, sessionmaker[Session]]]:
    engine = create_engine(f"sqlite:///{(tmp_path / 'baseline.sqlite3').as_posix()}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)

    def override_db() -> Iterator[Session]:
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")
    yield client, factory
    asyncio.run(client.aclose())
    app.dependency_overrides.clear()
    engine.dispose()


def test_training_authentication_staleness_and_deletion(
    client_db: tuple[AsyncClient, sessionmaker[Session]],
) -> None:
    client, factory = client_db

    async def run() -> None:
        profile_ids = []
        for label in ("P1", "P2"):
            response = await client.post(
                "/api/v1/profiles", json={"display_name": label}
            )
            profile_ids.append(response.json()["id"])
        assert (await client.post("/api/v1/models/train")).status_code == 409
        for profile_id, base in zip(profile_ids, (80, 250), strict=True):
            for i in range(6):
                timing = sequence(base + i, base - 15 + i)
                response = await client.post(
                    f"/api/v1/profiles/{profile_id}/samples",
                    json={
                        "consent_acknowledged": True,
                        "session_id": "747a3880-e54c-4d99-a010-d9ab67999a46"
                        if i < 3
                        else "747a3880-e54c-4d99-a010-d9ab67999a47",
                        "challenge_version": "fixed-1",
                        "feature_version": "timing-1",
                        "timing_sequence": timing.model_dump(),
                    },
                )
                assert response.status_code == 201

        trained = await client.post("/api/v1/models/train")
        assert trained.status_code == 200
        assert len(trained.json()["trained_profiles"]) == 2
        status = (await client.get("/api/v1/models/status")).json()
        assert {entry["status"] for entry in status["profiles"]} == {"ready"}

        def attempt(profile_id: int, timing: TimingSequence) -> dict:
            return {
                "profile_id": profile_id,
                "sample": {
                    "consent_acknowledged": True,
                    "session_id": "747a3880-e54c-4d99-a010-d9ab67999a48",
                    "challenge_version": "fixed-1",
                    "feature_version": "timing-1",
                    "timing_sequence": timing.model_dump(),
                },
            }

        accepted = await client.post(
            "/api/v1/authenticate", json=attempt(profile_ids[0], sequence(85, 70))
        )
        rejected = await client.post(
            "/api/v1/authenticate", json=attempt(profile_ids[0], sequence(255, 240))
        )
        assert accepted.status_code == rejected.status_code == 200
        assert accepted.json()["accepted"] is True
        assert rejected.json()["accepted"] is False
        assert accepted.json()["similarity_score"] > rejected.json()["similarity_score"]
        assert (
            accepted.json()["similarity_score"] > accepted.json()["decision_threshold"]
        )
        assert "timing_sequence" not in accepted.json()

        extra = attempt(profile_ids[0], sequence(87, 72))["sample"]
        assert (
            await client.post(f"/api/v1/profiles/{profile_ids[0]}/samples", json=extra)
        ).status_code == 201
        assert (
            await client.post(
                "/api/v1/authenticate", json=attempt(profile_ids[0], sequence(85, 70))
            )
        ).status_code == 409
        assert all(
            entry["status"] == "stale"
            for entry in (await client.get("/api/v1/models/status")).json()["profiles"]
        )

        assert (
            await client.delete(f"/api/v1/profiles/{profile_ids[0]}")
        ).status_code == 204
        with factory() as db:
            assert db.get(BaselineArtifact, profile_ids[0]) is None
            assert (
                db.scalar(
                    select(BaselineArtifact).where(
                        BaselineArtifact.profile_id == profile_ids[1]
                    )
                )
                is not None
            )

    asyncio.run(run())
