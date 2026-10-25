"""SQLite snapshot handling for the pure baseline module."""

import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.baseline import Recording
from app.database import TypingSample
from app.schemas import CHALLENGE_VERSION, FEATURE_VERSION, TimingSequence


def load_snapshot(db: Session) -> tuple[list[Recording], str]:
    rows = db.scalars(select(TypingSample).order_by(TypingSample.id)).all()
    serialized = []
    recordings = []
    for row in rows:
        if (
            row.challenge_version != CHALLENGE_VERSION
            or row.feature_version != FEATURE_VERSION
        ):
            raise ValueError("Stored sample version is unsupported")
        sequence = TimingSequence.model_validate(row.timing_sequence)
        recordings.append(Recording(row.id, row.profile_id, row.session_id, sequence))
        serialized.append(
            (
                row.id,
                row.profile_id,
                row.session_id,
                row.challenge_version,
                row.feature_version,
                sequence.model_dump(),
            )
        )
    fingerprint = hashlib.sha256(
        json.dumps(serialized, sort_keys=True, allow_nan=False).encode("utf-8")
    ).hexdigest()
    return recordings, fingerprint
