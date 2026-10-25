"""Versioned timing-only API contracts."""

import os
from datetime import datetime
from math import isclose, isfinite
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CHALLENGE_VERSION = "fixed-1"
FEATURE_VERSION = "timing-1"
CHALLENGE_LENGTH = len("the quick brown fox jumps over the lazy dog.")
ENROLLMENT_TARGET = int(os.environ.get("KEYRHYTHM_ENROLLMENT_TARGET", "10"))
if not 1 <= ENROLLMENT_TARGET <= 1000:
    raise ValueError("KEYRHYTHM_ENROLLMENT_TARGET must be between 1 and 1000")
PAUSE_THRESHOLD_MS = 750.0


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProfileCreate(StrictModel):
    display_name: str = Field(min_length=1, max_length=80)

    @field_validator("display_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Display label cannot be blank")
        return value


class ProfileResponse(StrictModel):
    id: int
    display_name: str
    created_at: datetime
    sample_count: int
    enrollment_target: int = ENROLLMENT_TARGET
    enrollment_status: Literal["collecting", "ready"]


class TimingSequence(StrictModel):
    hold_ms: list[float]
    down_down_ms: list[float]
    flight_ms: list[float]
    long_pauses: list[bool]
    total_ms: float

    @model_validator(mode="after")
    def validate_sequence(self) -> Self:
        n = CHALLENGE_LENGTH
        if (
            len(self.hold_ms),
            len(self.down_down_ms),
            len(self.flight_ms),
            len(self.long_pauses),
        ) != (n, n - 1, n - 1, n - 1):
            raise ValueError("Timing arrays must align with every challenge position")
        if not all(isfinite(x) and 0 < x <= 5000 for x in self.hold_ms):
            raise ValueError("Hold durations must be finite and within (0, 5000] ms")
        if not all(isfinite(x) and 0 < x <= 10000 for x in self.down_down_ms):
            raise ValueError(
                "Down-to-down intervals must be finite and within (0, 10000] ms"
            )
        if not all(isfinite(x) and -5000 <= x <= 10000 for x in self.flight_ms):
            raise ValueError(
                "Flight intervals must be finite and within [-5000, 10000] ms"
            )
        if not isfinite(self.total_ms) or not 0 < self.total_ms <= 120000:
            raise ValueError("Total duration must be finite and within (0, 120000] ms")
        for i, interval in enumerate(self.down_down_ms):
            if not isclose(interval, self.hold_ms[i] + self.flight_ms[i], abs_tol=0.1):
                raise ValueError("Flight and down-to-down intervals are inconsistent")
            if self.long_pauses[i] != (self.flight_ms[i] >= PAUSE_THRESHOLD_MS):
                raise ValueError("Long-pause flags are inconsistent")
        if not isclose(
            self.total_ms, sum(self.down_down_ms) + self.hold_ms[-1], abs_tol=0.1
        ):
            raise ValueError("Total duration is inconsistent")
        return self


class SampleCreate(StrictModel):
    consent_acknowledged: Literal[True]
    session_id: UUID
    challenge_version: str
    feature_version: str
    timing_sequence: TimingSequence

    @model_validator(mode="after")
    def check_versions(self) -> Self:
        if (
            self.challenge_version != CHALLENGE_VERSION
            or self.feature_version != FEATURE_VERSION
        ):
            raise ValueError("Unsupported challenge or feature version")
        return self


class SampleResponse(StrictModel):
    id: int
    profile_id: int
    created_at: datetime
    sample_count: int


class SampleMetadata(StrictModel):
    id: int
    created_at: datetime
    session_id: UUID
    challenge_version: str
    feature_version: str


class SamplesResponse(StrictModel):
    profile_id: int
    sample_count: int
    samples: list[SampleMetadata]


class CalibrationResponse(StrictModel):
    false_acceptance_rate: float
    false_rejection_rate: float
    genuine_count: int
    impostor_count: int
    session_disjoint: bool


class TrainedProfileResponse(StrictModel):
    profile_id: int
    training_count: int
    validation_count: int
    calibration: CalibrationResponse


class TrainResponse(StrictModel):
    model_version: str
    trained_profiles: list[TrainedProfileResponse]
    skipped_profile_ids: list[int]


class ModelProfileStatus(StrictModel):
    profile_id: int
    sample_count: int
    status: Literal["needs_data", "needs_training", "stale", "ready"]
    training_count: int | None = None
    validation_count: int | None = None
    calibration: CalibrationResponse | None = None


class ModelStatusResponse(StrictModel):
    model_version: str
    minimum_samples_per_profile: int
    minimum_profiles: int
    eligible_profile_count: int
    profiles: list[ModelProfileStatus]


class AuthenticationRequest(StrictModel):
    profile_id: int
    sample: SampleCreate


class AuthenticationResponse(StrictModel):
    profile_id: int
    similarity_score: float
    decision_threshold: float
    distance: float
    accepted: bool
    model_version: str
    feature_matrix_version: str
    calibration: CalibrationResponse
    explanation: str
