"""Held-out comparison, leakage audit, saved results and metric boundaries."""

import asyncio
from collections.abc import Iterator
from pathlib import Path
from uuid import NAMESPACE_DNS, uuid5

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

torch = pytest.importorskip("torch")

from app.baseline_service import load_snapshot
from app.database import Base, Profile, SiameseArtifact, TypingSample, get_db
from app.evaluation import Trial, restore_splits, summarize_trials
from app.main import app
from app.schemas import CHALLENGE_LENGTH, TimingSequence
from app.siamese import TrainingConfig, train
from app.siamese_service import save_training


def sequence(hold: float, gap: float) -> TimingSequence:
    n = CHALLENGE_LENGTH
    return TimingSequence(
        hold_ms=[hold + (i % 3) for i in range(n)],
        down_down_ms=[hold + gap + (i % 3) for i in range(n - 1)],
        flight_ms=[gap] * (n - 1),
        long_pauses=[False] * (n - 1),
        total_ms=sum(hold + gap + (i % 3) for i in range(n - 1))
        + hold + ((n - 1) % 3),
    )


def test_metric_denominators_and_reporting_gate() -> None:
    trials = [
        Trial(1, index, True, 0.8, 0.5, 0.3, True)
        for index in range(20)
    ] + [
        Trial(1, index + 20, False, 0.2, 0.5, -0.3, False)
        for index in range(20)
    ]
    metrics, roc = summarize_trials(trials)
    assert (metrics["true_positive"], metrics["true_negative"]) == (20, 20)
    assert metrics["false_acceptance_rate"] == metrics["false_rejection_rate"] == 0
    assert metrics["roc_auc"] == 1
    assert metrics["equal_error_rate"] == 0
    assert roc[0]["false_positive_rate"] == roc[0]["true_positive_rate"] == 0
    assert roc[-1]["false_positive_rate"] == roc[-1]["true_positive_rate"] == 1
    too_small, _ = summarize_trials(trials[:19] + trials[20:])
    assert too_small["roc_auc"] is too_small["equal_error_rate"] is None
    assert not too_small["auc_eer_supported"]


@pytest.fixture
def prepared(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[AsyncClient, sessionmaker[Session], Path]]:
    import app.siamese_service as service

    monkeypatch.setattr(service, "ARTIFACT_DIR", tmp_path / "artifacts")
    engine = create_engine(f"sqlite:///{(tmp_path / 'evaluation.sqlite3').as_posix()}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)

    def override_db() -> Iterator[Session]:
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")
    yield client, factory, service.ARTIFACT_DIR
    asyncio.run(client.aclose())
    app.dependency_overrides.clear()
    engine.dispose()


def test_same_test_trials_saved_plots_staleness_and_deletion(
    prepared: tuple[AsyncClient, sessionmaker[Session], Path]
) -> None:
    client, factory, artifact_dir = prepared

    async def run() -> None:
        assert (await client.post("/api/v1/experiments/evaluate")).status_code == 409
        with factory() as db:
            for profile_id in (1, 2, 3):
                db.add(Profile(id=profile_id, display_name=f"P{profile_id}"))
                for index in range(10):
                    timing = sequence(
                        70 + profile_id * 90 + index,
                        45 + profile_id * 80 + index,
                    )
                    session = 0 if index < 4 else 1 if index < 7 else 2
                    db.add(TypingSample(
                        profile_id=profile_id,
                        session_id=str(uuid5(NAMESPACE_DNS, f"{profile_id}-{session}")),
                        challenge_version="fixed-1",
                        feature_version="timing-1",
                        timing_sequence=timing.model_dump(),
                    ))
            db.commit()
            recordings, fingerprint = load_snapshot(db)
            result = train(recordings, TrainingConfig(epochs=1, batch_size=16))
            save_training(db, result, fingerprint)
            artifact = db.get(SiameseArtifact, 1)
            assert artifact is not None
            checkpoint_name = artifact.checkpoint_name
            corrupt = result.metadata()["splits"]
            corrupt["1"]["test_ids"][0] = corrupt["1"]["train_ids"][0]
            with pytest.raises(ValueError, match="overlapping"):
                restore_splits(recordings, corrupt)

        response = await client.post("/api/v1/experiments/evaluate")
        assert response.status_code == 200, response.text
        experiment = response.json()
        experiment_id = experiment["id"]
        state = experiment["result"]
        assert state["profile_count"] == 3
        assert state["test_recording_count"] == 9
        assert state["trial_count_per_model"] == 27
        baseline = state["models"]["baseline"]
        neural = state["models"]["siamese"]
        assert baseline["metrics"]["genuine_count"] == neural["metrics"]["genuine_count"] == 9
        assert baseline["metrics"]["impostor_count"] == neural["metrics"]["impostor_count"] == 18
        assert baseline["metrics"]["roc_auc"] is neural["metrics"]["roc_auc"] is None
        for model in (baseline, neural):
            operating = next(
                point for point in model["roc"]
                if point["decision_margin_threshold"] == 0
            )
            assert operating["false_positive_rate"] == model["metrics"]["false_acceptance_rate"]
            assert operating["true_positive_rate"] == 1 - model["metrics"]["false_rejection_rate"]
        assert [
            (item["claimed_profile_id"], item["recording_id"], item["genuine"])
            for item in baseline["trials"]
        ] == [
            (item["claimed_profile_id"], item["recording_id"], item["genuine"])
            for item in neural["trials"]
        ]
        assert [item["reference_count"] for item in state["reference_count_effect"]] == [2, 4]
        assert (await client.post("/api/v1/experiments/evaluate")).json()["id"] == experiment_id
        assert len((await client.get("/api/v1/experiments")).json()) == 1
        assert (await client.get(f"/api/v1/experiments/{experiment_id}")).json() == experiment
        roc = await client.get(f"/api/v1/experiments/{experiment_id}/plots/roc.svg")
        matrix = await client.get(f"/api/v1/experiments/{experiment_id}/plots/confusion.svg")
        assert roc.status_code == matrix.status_code == 200
        assert "<polyline" in roc.text
        assert "Held-out confusion matrices" in matrix.text
        assert "timing_sequence" not in roc.text + matrix.text

        with factory() as db:
            first_sample = db.scalar(select(TypingSample).order_by(TypingSample.id))
            assert first_sample is not None
            first_sample.timing_sequence = sequence(900, 700).model_dump()
            db.commit()
        stale = await client.post("/api/v1/experiments/evaluate")
        assert stale.status_code == 409
        assert "retrain" in stale.json()["detail"]
        assert (await client.delete("/api/v1/profiles/1")).status_code == 204
        assert not (artifact_dir / checkpoint_name).exists()
        assert (await client.get("/api/v1/experiments")).json() == []

    asyncio.run(run())
