"""Persist immutable comparison runs and reuse a saved run for the same model."""

import hashlib
import subprocess
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.baseline_service import load_snapshot
from app.database import Experiment, SiameseArtifact
from app.evaluation import PROTOCOL_VERSION, evaluate_models


def code_revision() -> dict:
    root = Path(__file__).resolve().parents[2]
    command = ["git", "-c", f"safe.directory={root.as_posix()}", "-C", str(root)]
    try:
        revision = subprocess.run(
            [*command, "rev-parse", "HEAD"], capture_output=True, text=True,
            check=True, timeout=3,
        ).stdout.strip()
        dirty = bool(subprocess.run(
            [*command, "status", "--porcelain"], capture_output=True, text=True,
            check=True, timeout=3,
        ).stdout.strip())
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return {"commit": None, "working_tree_dirty": None}
    return {"commit": revision, "working_tree_dirty": dirty}


def evaluation_code_fingerprint() -> str:
    app_dir = Path(__file__).resolve().parent
    digest = hashlib.sha256()
    for name in (
        "baseline.py", "baseline_service.py", "evaluation.py",
        "evaluation_service.py", "schemas.py",
        "siamese.py", "siamese_service.py",
    ):
        digest.update(name.encode("utf-8"))
        digest.update((app_dir / name).read_bytes())
    return digest.hexdigest()


def run_evaluation(db: Session) -> Experiment:
    try:
        recordings, fingerprint = load_snapshot(db)
    except (ValueError, TypeError) as exc:
        raise ValueError("Stored timing data is invalid") from exc
    artifact = db.get(SiameseArtifact, 1)
    if artifact is None:
        raise ValueError("Train the Siamese model before evaluation")
    if artifact.dataset_fingerprint != fingerprint:
        raise ValueError("Enrollment data changed; retrain the Siamese model")
    source_fingerprint = evaluation_code_fingerprint()
    for previous in db.scalars(
        select(Experiment).where(
            Experiment.dataset_fingerprint == fingerprint,
            Experiment.protocol_version == PROTOCOL_VERSION,
        ).order_by(Experiment.id.desc())
    ):
        if (
            previous.state.get("neural_checkpoint_name") == artifact.checkpoint_name
            and previous.state.get("evaluation_code_fingerprint") == source_fingerprint
        ):
            return previous
    result = evaluate_models(recordings, artifact, fingerprint)
    result["neural_checkpoint_name"] = artifact.checkpoint_name
    result["evaluation_code_fingerprint"] = source_fingerprint
    result["code_revision"] = code_revision()
    experiment = Experiment(
        dataset_fingerprint=fingerprint,
        protocol_version=PROTOCOL_VERSION,
        state=result,
    )
    db.add(experiment)
    db.commit()
    db.refresh(experiment)
    return experiment
