"""Checkpoint persistence and safe loading for the local neural verifier."""

from __future__ import annotations

import os
from math import isfinite
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.baseline import FEATURE_MATRIX_VERSION, ErrorRates, Scaler
from app.database import SiameseArtifact
from app.schemas import SIAMESE_MODEL_VERSION

if TYPE_CHECKING:
    from app.siamese import ProfileCalibration, SiameseNetwork, TrainingResult

ARTIFACT_DIR = Path(__file__).resolve().parents[1] / "artifacts"


class CheckpointCleanupError(RuntimeError):
    pass


def checkpoint_path(name: str) -> Path:
    if not name.startswith("siamese-") or not name.endswith(".pt"):
        raise ValueError("Invalid checkpoint name")
    try:
        token = name.removeprefix("siamese-").removesuffix(".pt")
        if str(UUID(token)) != token:
            raise ValueError("Invalid checkpoint name")
    except ValueError as exc:
        raise ValueError("Invalid checkpoint name") from exc
    return ARTIFACT_DIR / name


def remove_checkpoint(name: str) -> None:
    checkpoint_path(name).unlink(missing_ok=True)


def save_training(db: Session, result: TrainingResult, fingerprint: str) -> None:
    import torch

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    name = f"siamese-{uuid4()}.pt"
    final = checkpoint_path(name)
    temporary = final.with_suffix(".tmp")
    old = db.get(SiameseArtifact, 1)
    old_name = old.checkpoint_name if old else None
    try:
        torch.save(result.state_dict, temporary)
        os.replace(temporary, final)
        if old is None:
            db.add(SiameseArtifact(
                id=1,
                model_version=SIAMESE_MODEL_VERSION,
                dataset_fingerprint=fingerprint,
                checkpoint_name=name,
                state=result.metadata(),
            ))
        else:
            old.model_version = SIAMESE_MODEL_VERSION
            old.dataset_fingerprint = fingerprint
            old.checkpoint_name = name
            old.state = result.metadata()
        db.commit()
    except Exception:
        db.rollback()
        temporary.unlink(missing_ok=True)
        final.unlink(missing_ok=True)
        raise
    if old_name:
        try:
            remove_checkpoint(old_name)
        except (OSError, ValueError) as exc:
            raise CheckpointCleanupError(
                "Neural model saved, but the previous checkpoint could not be removed"
            ) from exc


def load_trained(
    artifact: SiameseArtifact, fingerprint: str, profile_id: int
) -> tuple[SiameseNetwork, Scaler, ProfileCalibration]:
    import torch

    from app.siamese import ProfileCalibration, SiameseNetwork, TrainingConfig

    if artifact.model_version != SIAMESE_MODEL_VERSION or artifact.dataset_fingerprint != fingerprint:
        raise ValueError("Neural model is stale; retrain it")
    data = artifact.state
    if (data["model_version"] != SIAMESE_MODEL_VERSION
        or data["feature_matrix_version"] != FEATURE_MATRIX_VERSION):
        raise ValueError("Unsupported neural model version")
    config = TrainingConfig(**data["config"])
    if not 4 <= config.embedding_dim <= 256:
        raise ValueError("Invalid embedding dimension")
    scaler = Scaler(
        tuple(float(value) for value in data["scaler"]["center"]),
        tuple(float(value) for value in data["scaler"]["scale"]),
    )
    profile_data = data["profiles"][str(profile_id)]
    profile = ProfileCalibration(
        tuple(float(value) for value in profile_data["centroid"]),
        float(profile_data["threshold_distance"]),
        ErrorRates(**profile_data["calibration"]),
    )
    if (len(scaler.center) != 3 or len(scaler.scale) != 3
        or any(not isfinite(value) for value in scaler.center)
        or any(not isfinite(value) or value <= 0 for value in scaler.scale)
        or len(profile.centroid) != config.embedding_dim
        or any(not isfinite(value) for value in profile.centroid)
        or not isfinite(profile.threshold_distance)
        or profile.threshold_distance < 0):
        raise ValueError("Invalid neural centroid")
    network = SiameseNetwork(config.embedding_dim)
    weights = torch.load(checkpoint_path(artifact.checkpoint_name),
                         map_location="cpu", weights_only=True)
    network.load_state_dict(weights, strict=True)
    network.eval()
    return network, scaler, profile
