"""Neural shape, partition, checkpoint, API and privacy checks."""

import asyncio
from collections.abc import Iterator
from math import isfinite
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

torch = pytest.importorskip("torch")

from app.baseline import Recording
from app.database import Base, SiameseArtifact, get_db
from app.main import app
from app.schemas import CHALLENGE_LENGTH, TimingSequence
from app.siamese import (
    SiameseNetwork,
    TrainingConfig,
    contrastive_loss,
    make_pairs,
    prepare_splits,
    score_sample,
    train,
)
from app.siamese_service import load_trained, save_training


def sequence(hold: float, gap: float) -> TimingSequence:
    n = CHALLENGE_LENGTH
    return TimingSequence(
        hold_ms=[hold + (i % 5) for i in range(n)],
        down_down_ms=[hold + gap + (i % 5) for i in range(n - 1)],
        flight_ms=[gap] * (n - 1),
        long_pauses=[False] * (n - 1),
        total_ms=sum(hold + gap + (i % 5) for i in range(n - 1))
        + hold + ((n - 1) % 5),
    )


def recordings() -> list[Recording]:
    return [
        Recording(
            sample_id=profile_id * 100 + index,
            profile_id=profile_id,
            session_id=f"session-{profile_id}-{0 if index < 4 else 1 if index < 7 else 2}",
            timing_sequence=sequence(70 + 90 * profile_id + index, 45 + 80 * profile_id + index),
        )
        for profile_id in (1, 2, 3)
        for index in range(10)
    ]


def test_shared_encoder_shapes_pairs_and_partition_boundaries() -> None:
    network = SiameseNetwork(16)
    left = torch.zeros(2, 3, CHALLENGE_LENGTH)
    first, second = network(left, left)
    assert first.shape == second.shape == (2, 16)
    assert torch.allclose(first, second)
    assert contrastive_loss(first, second, torch.ones(2), 1.0).item() < 1e-10

    splits = prepare_splits(recordings())
    assert all(split.session_disjoint for split in splits.values())
    for split in splits.values():
        assert (len(split.train), len(split.validation), len(split.test)) == (4, 3, 3)
        partitions = [
            {item.sample_id for item in records}
            for records in (split.train, split.validation, split.test)
        ]
        assert not partitions[0] & partitions[1]
        assert not partitions[0] & partitions[2]
        assert not partitions[1] & partitions[2]
    training = [item for split in splits.values() for item in split.train]
    pairs = make_pairs(training, seed=42)
    by_id = {item.sample_id: item.profile_id for item in training}
    assert sum(pair.same_profile for pair in pairs) == len(pairs) // 2
    assert all(
        pair.same_profile == (by_id[pair.left_id] == by_id[pair.right_id])
        for pair in pairs
    )
    assert pairs == make_pairs(training, seed=42)
    with pytest.raises(ValueError, match="Duplicate"):
        prepare_splits(recordings() + [recordings()[0]])


def test_training_checkpoint_and_inference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.siamese_service as service

    monkeypatch.setattr(service, "ARTIFACT_DIR", tmp_path / "artifacts")
    items = recordings()
    result = train(items, TrainingConfig(epochs=2, batch_size=16))
    assert len(result.history) == 2
    assert result.best_epoch in (1, 2)
    assert all(
        isfinite(epoch["train_loss"]) and isfinite(epoch["validation_loss"])
        for epoch in result.history
    )
    test_ids = {
        item.sample_id for split in result.splits.values() for item in split.test
    }
    assert not test_ids & {
        item.sample_id
        for split in result.splits.values()
        for item in (*split.train, *split.validation)
    }
    changed_test = [
        Recording(item.sample_id, item.profile_id, item.session_id, sequence(800, 700))
        if item.sample_id in test_ids else item
        for item in items
    ]
    repeated = train(changed_test, TrainingConfig(epochs=2, batch_size=16))
    assert result.history == repeated.history
    assert result.scaler == repeated.scaler
    assert result.profiles == repeated.profiles
    engine = create_engine(f"sqlite:///{(tmp_path / 'model.sqlite3').as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        save_training(db, result, "fingerprint")
        artifact = db.get(SiameseArtifact, 1)
        assert artifact is not None
        assert service.checkpoint_path(artifact.checkpoint_name).is_file()
        network, scaler, profile = load_trained(artifact, "fingerprint", 1)
        score = score_sample(network, scaler, profile, sequence(161, 126))
        assert all(isfinite(value) for value in score[:3])
        assert score[0] > 0
        with pytest.raises(ValueError, match="stale"):
            load_trained(artifact, "changed", 1)
    engine.dispose()


@pytest.fixture
def client_db(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[AsyncClient, sessionmaker[Session], Path]]:
    import app.siamese_service as service

    monkeypatch.setattr(service, "ARTIFACT_DIR", tmp_path / "artifacts")
    engine = create_engine(f"sqlite:///{(tmp_path / 'api.sqlite3').as_posix()}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)

    def override_db() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")
    yield client, factory, service.ARTIFACT_DIR
    asyncio.run(client.aclose())
    app.dependency_overrides.clear()
    engine.dispose()


def test_api_training_status_inference_staleness_and_deletion(
    client_db: tuple[AsyncClient, sessionmaker[Session], Path],
) -> None:
    client, factory, artifact_dir = client_db

    async def run() -> None:
        before = await client.post("/api/v1/models/siamese/train", json={"epochs": 1})
        assert before.status_code == 409
        assert "3 profiles" in before.json()["detail"]
        ids = []
        for profile_id in (1, 2, 3):
            created = await client.post(
                "/api/v1/profiles", json={"display_name": f"P{profile_id}"}
            )
            ids.append(created.json()["id"])
        for profile_id in ids:
            for index in range(10):
                timing = sequence(70 + 90 * profile_id + index, 45 + 80 * profile_id + index)
                response = await client.post(
                    f"/api/v1/profiles/{profile_id}/samples",
                    json={
                        "consent_acknowledged": True,
                        "session_id": (
                            "747a3880-e54c-4d99-a010-d9ab67999a46"
                            if index < 4 else
                            "747a3880-e54c-4d99-a010-d9ab67999a47"
                            if index < 7 else
                            "747a3880-e54c-4d99-a010-d9ab67999a48"
                        ),
                        "challenge_version": "fixed-1",
                        "feature_version": "timing-1",
                        "timing_sequence": timing.model_dump(),
                    },
                )
                assert response.status_code == 201
        trained = await client.post("/api/v1/models/siamese/train", json={"epochs": 2})
        assert trained.status_code == 200, trained.text
        assert len(trained.json()["history"]) == 2
        assert len(trained.json()["profiles"]) == 3
        assert (await client.get("/api/v1/models/siamese/status")).json()["status"] == "ready"
        with factory() as db:
            artifact = db.get(SiameseArtifact, 1)
            assert artifact is not None
            checkpoint_name = artifact.checkpoint_name
            assert set(artifact.state["splits"][str(ids[0])]) == {
                "train_ids", "validation_ids", "test_ids", "session_disjoint"
            }

        sample = {
            "consent_acknowledged": True,
            "session_id": "747a3880-e54c-4d99-a010-d9ab67999a49",
            "challenge_version": "fixed-1",
            "feature_version": "timing-1",
            "timing_sequence": sequence(161, 126).model_dump(),
        }
        attempt = {"profile_id": ids[0], "model_type": "siamese", "sample": sample}
        verification = await client.post("/api/v1/authenticate", json=attempt)
        assert verification.status_code == 200, verification.text
        assert verification.json()["model_type"] == "siamese"
        assert verification.json()["similarity_score"] > 0
        assert "timing_sequence" not in verification.text

        changed = await client.post(f"/api/v1/profiles/{ids[0]}/samples", json=sample)
        assert changed.status_code == 201
        assert (await client.get("/api/v1/models/siamese/status")).json()["status"] == "stale"
        assert (await client.post("/api/v1/authenticate", json=attempt)).status_code == 409
        assert (await client.delete(f"/api/v1/profiles/{ids[0]}")).status_code == 204
        assert not (artifact_dir / checkpoint_name).exists()
        with factory() as db:
            assert db.get(SiameseArtifact, 1) is None

    asyncio.run(run())
