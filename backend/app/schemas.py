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
SIAMESE_MODEL_VERSION = "siamese-cnn-v1"
SIAMESE_MIN_PROFILES = 3
SIAMESE_MIN_SAMPLES_PER_PROFILE = 10


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
    model_type: Literal["baseline", "siamese"] = "baseline"


class AuthenticationResponse(StrictModel):
    profile_id: int
    model_type: Literal["baseline", "siamese"]
    similarity_score: float
    decision_threshold: float
    distance: float
    accepted: bool
    model_version: str
    feature_matrix_version: str
    calibration: CalibrationResponse
    explanation: str


class VerificationTrialResponse(StrictModel):
    id: int
    profile_id: int
    created_at: datetime
    model_type: Literal["baseline", "siamese"]
    model_version: str
    similarity_score: float
    decision_threshold: float
    accepted: bool


class SiameseTrainRequest(StrictModel):
    epochs: int = Field(default=20, ge=1, le=100)
    batch_size: int = Field(default=32, ge=4, le=256)
    learning_rate: float = Field(default=0.001, gt=0, le=0.1, allow_inf_nan=False)
    embedding_dim: int = Field(default=32, ge=4, le=256)
    margin: float = Field(default=1.0, gt=0, le=2, allow_inf_nan=False)
    seed: int = Field(default=42, ge=0, le=2**31 - 1)


class LossEpoch(StrictModel):
    epoch: int
    train_loss: float
    validation_loss: float


class SiameseProfileResult(StrictModel):
    profile_id: int
    training_count: int
    validation_count: int
    held_out_count: int
    session_disjoint: bool
    calibration: CalibrationResponse


class SiameseTrainResponse(StrictModel):
    model_version: str
    best_epoch: int
    history: list[LossEpoch]
    profiles: list[SiameseProfileResult]
    skipped_profile_ids: list[int]


class SiameseStatusResponse(StrictModel):
    model_version: str
    status: Literal["needs_data", "needs_training", "stale", "ready"]
    minimum_profiles: int
    minimum_samples_per_profile: int
    eligible_profile_count: int
    best_epoch: int | None = None
    history: list[LossEpoch] = Field(default_factory=list)
    profiles: list[SiameseProfileResult] = Field(default_factory=list)


class SplitManifest(StrictModel):
    train_ids: list[int]
    validation_ids: list[int]
    test_ids: list[int]
    session_disjoint: bool


class EvaluationMetrics(StrictModel):
    genuine_count: int
    impostor_count: int
    true_positive: int
    false_negative: int
    false_positive: int
    true_negative: int
    false_acceptance_rate: float
    false_rejection_rate: float
    precision: float | None
    recall: float
    roc_auc: float | None
    equal_error_rate: float | None
    auc_eer_supported: bool


class RocPoint(StrictModel):
    decision_margin_threshold: float
    false_positive_rate: float
    true_positive_rate: float


class TrialResult(StrictModel):
    claimed_profile_id: int
    recording_id: int
    genuine: bool
    similarity_score: float
    decision_threshold: float
    decision_margin: float
    accepted: bool


class EvaluationCalibration(StrictModel):
    false_acceptance_rate: float
    false_rejection_rate: float
    genuine_count: int
    impostor_count: int
    session_disjoint: bool
    training_count: int
    validation_count: int


class ModelEvaluation(StrictModel):
    metrics: EvaluationMetrics
    roc: list[RocPoint]
    thresholds: dict[str, float]
    validation_calibration: dict[str, EvaluationCalibration]
    trials: list[TrialResult]


class ReferenceCountEffect(StrictModel):
    reference_count: int
    baseline: EvaluationMetrics
    siamese: EvaluationMetrics


class CodeRevision(StrictModel):
    commit: str | None
    working_tree_dirty: bool | None


class ExperimentResult(StrictModel):
    protocol_version: str
    dataset_fingerprint: str
    challenge_version: str
    timing_feature_version: str
    feature_matrix_version: str
    model_versions: dict[str, str]
    training_configuration: SiameseTrainRequest
    training_history: list[LossEpoch]
    best_epoch: int
    torch_version: str
    split_configuration: dict[str, SplitManifest]
    profile_count: int
    sample_count: int
    test_recording_count: int
    trial_count_per_model: int
    models: dict[str, ModelEvaluation]
    reference_count_effect: list[ReferenceCountEffect]
    limitations: list[str]
    neural_checkpoint_name: str
    evaluation_code_fingerprint: str
    code_revision: CodeRevision


class ExperimentResponse(StrictModel):
    id: int
    created_at: datetime
    result: ExperimentResult


class ExperimentSummary(StrictModel):
    id: int
    created_at: datetime
    dataset_fingerprint: str
    protocol_version: str
    profile_count: int
    test_recording_count: int
    baseline: EvaluationMetrics
    siamese: EvaluationMetrics
