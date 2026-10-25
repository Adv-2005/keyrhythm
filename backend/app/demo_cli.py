"""Create an isolated, explicitly synthetic dataset for a software walkthrough.

Usage from backend/: python -m app.demo_cli --output data/synthetic-demo
The output directory must be empty. Never use these records for research claims.
"""

import argparse
import os
import sys
from pathlib import Path
from uuid import NAMESPACE_DNS, uuid5


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("data/synthetic-demo"))
    parser.add_argument("--epochs", type=int, default=2)
    args = parser.parse_args()
    output = args.output.resolve()
    if args.epochs < 1 or args.epochs > 100:
        parser.error("--epochs must be between 1 and 100")
    if output.exists() and any(output.iterdir()):
        print(f"Output directory is not empty: {output}", file=sys.stderr)
        return 1
    output.mkdir(parents=True, exist_ok=True)
    database_file = output / "keyrhythm.sqlite3"
    os.environ["KEYRHYTHM_DATABASE_URL"] = f"sqlite:///{database_file.as_posix()}"
    os.environ["KEYRHYTHM_ARTIFACT_DIR"] = str(output / "artifacts")

    from app.baseline import fit_baselines
    from app.baseline_service import load_snapshot
    from app.database import (
        Base,
        BaselineArtifact,
        Profile,
        SessionLocal,
        TypingSample,
        engine,
    )
    from app.evaluation_service import run_evaluation
    from app.schemas import CHALLENGE_LENGTH, TimingSequence
    from app.siamese import TrainingConfig, train
    from app.siamese_service import save_training

    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        for profile_id in (1, 2, 3):
            db.add(Profile(id=profile_id, display_name=f"SYNTHETIC {profile_id:02d}"))
            for index in range(10):
                hold = 70 + profile_id * 90 + index
                gap = 45 + profile_id * 80 + index
                holds = [hold + position % 3 for position in range(CHALLENGE_LENGTH)]
                intervals = [hold + gap + position % 3 for position in range(CHALLENGE_LENGTH - 1)]
                timing = TimingSequence(
                    hold_ms=holds,
                    down_down_ms=intervals,
                    flight_ms=[gap] * (CHALLENGE_LENGTH - 1),
                    long_pauses=[False] * (CHALLENGE_LENGTH - 1),
                    total_ms=sum(intervals) + holds[-1],
                )
                session = 0 if index < 4 else 1 if index < 7 else 2
                db.add(TypingSample(
                    profile_id=profile_id,
                    session_id=str(uuid5(NAMESPACE_DNS, f"synthetic-{profile_id}-{session}")),
                    challenge_version="fixed-1",
                    feature_version="timing-1",
                    timing_sequence=timing.model_dump(),
                ))
        db.commit()
        recordings, fingerprint = load_snapshot(db)
        for model in fit_baselines(recordings).values():
            db.add(BaselineArtifact(
                profile_id=model.profile_id,
                model_version="baseline-distance-v1",
                dataset_fingerprint=fingerprint,
                state=model.to_json(),
            ))
        db.commit()
        result = train(recordings, TrainingConfig(epochs=args.epochs, batch_size=16))
        save_training(db, result, fingerprint)
        experiment = run_evaluation(db)

    print("SYNTHETIC SOFTWARE DEMO ONLY — no participant data or research result")
    print(f"Database: {database_file}")
    print(f"Artifacts: {output / 'artifacts'}")
    print(f"Experiment ID: {experiment.id}")
    print("Set KEYRHYTHM_DATABASE_URL and KEYRHYTHM_ARTIFACT_DIR to these paths before starting the API.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
