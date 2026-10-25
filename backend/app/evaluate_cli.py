"""Run the saved known-user comparison from a local shell.

Usage from backend/: python -m app.evaluate_cli
"""

import json
import sys

from app.database import Base, SessionLocal, engine


def main() -> int:
    try:
        from app.evaluation_service import run_evaluation
    except ImportError:
        print("Install backend/requirements-ml.txt before evaluation", file=sys.stderr)
        return 1
    Base.metadata.create_all(engine)
    try:
        with SessionLocal() as db:
            experiment = run_evaluation(db)
            result = experiment.state
            print(json.dumps({
                "experiment_id": experiment.id,
                "dataset_fingerprint": experiment.dataset_fingerprint,
                "profile_count": result["profile_count"],
                "test_recording_count": result["test_recording_count"],
                "baseline": result["models"]["baseline"]["metrics"],
                "siamese": result["models"]["siamese"]["metrics"],
            }, indent=2))
    except (ValueError, OSError, RuntimeError, KeyError) as exc:
        print(f"Evaluation unavailable: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
