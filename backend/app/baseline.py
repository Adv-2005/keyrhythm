"""Deterministic, training-only preprocessing and distance baseline.

This module has no HTTP or database dependency. Scores are similarities, not
probabilities; larger values mean a closer match to a profile prototype.
"""

from dataclasses import dataclass
from itertools import pairwise
from math import isfinite, sqrt
from statistics import median

from app.schemas import CHALLENGE_LENGTH, TimingSequence

MODEL_VERSION = "baseline-distance-v1"
FEATURE_MATRIX_VERSION = "baseline-features-v1"
MIN_SAMPLES_PER_PROFILE = 6
MIN_PROFILES = 2
CHANNELS = 3

FeatureMatrix = tuple[tuple[float, float, float], ...]


@dataclass(frozen=True)
class Recording:
    sample_id: int
    profile_id: int
    session_id: str
    timing_sequence: TimingSequence


@dataclass(frozen=True)
class RecordingSplit:
    train: tuple[Recording, ...]
    validation: tuple[Recording, ...]
    session_disjoint: bool


@dataclass(frozen=True)
class Scaler:
    center: tuple[float, float, float]
    scale: tuple[float, float, float]


@dataclass(frozen=True)
class ErrorRates:
    false_acceptance_rate: float
    false_rejection_rate: float
    genuine_count: int
    impostor_count: int


@dataclass(frozen=True)
class BaselineModel:
    profile_id: int
    scaler: Scaler
    prototype: FeatureMatrix
    threshold_distance: float
    train_ids: tuple[int, ...]
    validation_ids: tuple[int, ...]
    session_disjoint: bool
    calibration: ErrorRates

    def to_json(self) -> dict:
        return {
            "feature_matrix_version": FEATURE_MATRIX_VERSION,
            "scaler": {"center": self.scaler.center, "scale": self.scaler.scale},
            "prototype": self.prototype,
            "threshold_distance": self.threshold_distance,
            "train_ids": self.train_ids,
            "validation_ids": self.validation_ids,
            "session_disjoint": self.session_disjoint,
            "calibration": self.calibration.__dict__,
        }

    @classmethod
    def from_json(cls, profile_id: int, data: dict) -> "BaselineModel":
        if data["feature_matrix_version"] != FEATURE_MATRIX_VERSION:
            raise ValueError("Unsupported baseline feature version")
        scaler = Scaler(
            center=tuple(data["scaler"]["center"]),
            scale=tuple(data["scaler"]["scale"]),
        )
        prototype = tuple(tuple(row) for row in data["prototype"])
        threshold = float(data["threshold_distance"])
        if (
            len(scaler.center) != CHANNELS
            or len(scaler.scale) != CHANNELS
            or any(not isfinite(value) for value in scaler.center)
            or any(not isfinite(value) or value <= 0 for value in scaler.scale)
            or len(prototype) != CHALLENGE_LENGTH
            or any(
                len(row) != CHANNELS or any(not isfinite(value) for value in row)
                for row in prototype
            )
            or not isfinite(threshold)
            or threshold < 0
        ):
            raise ValueError("Invalid baseline prototype")
        return cls(
            profile_id=profile_id,
            scaler=scaler,
            prototype=prototype,
            threshold_distance=threshold,
            train_ids=tuple(data["train_ids"]),
            validation_ids=tuple(data["validation_ids"]),
            session_disjoint=bool(data["session_disjoint"]),
            calibration=ErrorRates(**data["calibration"]),
        )


class InsufficientDataError(ValueError):
    pass


def extract_features(sequence: TimingSequence | dict) -> FeatureMatrix:
    """Return 44 aligned rows: hold ms, down-to-down ms, and pause flag.

    The last position has no following key, so its interval and pause are zero.
    Revalidation also guards data read from SQLite against corruption.
    """
    valid = TimingSequence.model_validate(sequence)
    return tuple(
        (
            valid.hold_ms[i],
            valid.down_down_ms[i] if i < CHALLENGE_LENGTH - 1 else 0.0,
            float(valid.long_pauses[i]) if i < CHALLENGE_LENGTH - 1 else 0.0,
        )
        for i in range(CHALLENGE_LENGTH)
    )


def split_recordings(recordings: list[Recording]) -> RecordingSplit:
    """Reserve at least two genuine validation recordings, by session if feasible."""
    ordered = sorted(recordings, key=lambda item: item.sample_id)
    if len(ordered) < MIN_SAMPLES_PER_PROFILE:
        raise InsufficientDataError(
            f"At least {MIN_SAMPLES_PER_PROFILE} samples per profile are required"
        )
    sessions = list(dict.fromkeys(item.session_id for item in ordered))
    if len(sessions) > 1:
        selected: set[str] = set()
        for session_id in reversed(sessions):
            selected.add(session_id)
            validation = tuple(item for item in ordered if item.session_id in selected)
            train = tuple(item for item in ordered if item.session_id not in selected)
            if len(validation) >= 2 and len(train) >= 3:
                return RecordingSplit(train, validation, True)
            if len(train) < 3:
                break
    return RecordingSplit(tuple(ordered[:-2]), tuple(ordered[-2:]), False)


def fit_scaler(training: list[Recording]) -> Scaler:
    """Fit robust channel statistics using training recordings only."""
    matrices = [extract_features(item.timing_sequence) for item in training]
    if not matrices:
        raise InsufficientDataError("No training samples")
    columns: list[list[float]] = [[], []]
    for matrix in matrices:
        for position, row in enumerate(matrix):
            columns[0].append(row[0])
            if position < CHALLENGE_LENGTH - 1:
                columns[1].append(row[1])
    centers = [median(values) for values in columns]
    scales = [
        max(median(abs(value - centers[i]) for value in values) * 1.4826, floor)
        for i, (values, floor) in enumerate(zip(columns, (20.0, 30.0), strict=True))
    ]
    return Scaler((centers[0], centers[1], 0.0), (scales[0], scales[1], 1.0))


def normalize(matrix: FeatureMatrix, scaler: Scaler) -> FeatureMatrix:
    if len(matrix) != CHALLENGE_LENGTH or any(len(row) != CHANNELS for row in matrix):
        raise ValueError("Invalid feature matrix shape")
    if any(not isfinite(value) for row in matrix for value in row):
        raise ValueError("Non-finite feature value")
    if any(not isfinite(value) for value in scaler.center) or any(
        not isfinite(value) or value <= 0 for value in scaler.scale
    ):
        raise ValueError("Invalid scaler")
    return tuple(
        tuple(
            (value - scaler.center[i]) / scaler.scale[i] for i, value in enumerate(row)
        )
        for row in matrix
    )


def distance(left: FeatureMatrix, right: FeatureMatrix) -> float:
    if len(left) != CHALLENGE_LENGTH or len(right) != CHALLENGE_LENGTH:
        raise ValueError("Invalid feature matrix shape")
    squared = [
        (a - b) ** 2
        for lrow, rrow in zip(left, right, strict=True)
        for a, b in zip(lrow, rrow, strict=True)
    ]
    result = sqrt(sum(squared) / len(squared))
    if not isfinite(result):
        raise ValueError("Non-finite distance")
    return result


def error_rates(
    genuine: list[float], impostor: list[float], threshold: float
) -> ErrorRates:
    if not genuine or not impostor:
        raise InsufficientDataError("Both genuine and impostor trials are required")
    if not all(
        isfinite(value) and value >= 0 for value in (*genuine, *impostor, threshold)
    ):
        raise ValueError("Invalid score or threshold")
    return ErrorRates(
        false_acceptance_rate=sum(value < threshold for value in impostor)
        / len(impostor),
        false_rejection_rate=sum(value >= threshold for value in genuine)
        / len(genuine),
        genuine_count=len(genuine),
        impostor_count=len(impostor),
    )


def calibrate_threshold(
    genuine: list[float], impostor: list[float]
) -> tuple[float, ErrorRates]:
    """Choose validation threshold minimizing balanced error; ties reject more."""
    if not genuine or not impostor:
        raise InsufficientDataError("Validation needs genuine and impostor samples")
    values = sorted({*genuine, *impostor})
    candidates = [0.0, *((left + right) / 2 for left, right in pairwise(values))]
    candidates.append(values[-1] + 1e-9)
    threshold = min(
        candidates,
        key=lambda value: (
            (rates := error_rates(genuine, impostor, value)).false_acceptance_rate
            + rates.false_rejection_rate,
            rates.false_acceptance_rate,
            value,
        ),
    )
    return threshold, error_rates(genuine, impostor, threshold)


def fit_baselines(recordings: list[Recording]) -> dict[int, BaselineModel]:
    by_profile: dict[int, list[Recording]] = {}
    for item in recordings:
        by_profile.setdefault(item.profile_id, []).append(item)
    splits = {
        profile_id: split_recordings(items)
        for profile_id, items in by_profile.items()
        if len(items) >= MIN_SAMPLES_PER_PROFILE
    }
    if len(splits) < MIN_PROFILES:
        raise InsufficientDataError(
            f"At least {MIN_PROFILES} profiles with {MIN_SAMPLES_PER_PROFILE} samples each are required"
        )
    scaler = fit_scaler([item for split in splits.values() for item in split.train])
    normalized = {
        item.sample_id: normalize(extract_features(item.timing_sequence), scaler)
        for split in splits.values()
        for item in (*split.train, *split.validation)
    }
    calibration_sessions_disjoint = all(
        split.session_disjoint for split in splits.values()
    )
    models = {}
    for profile_id, split in splits.items():
        prototype = tuple(
            tuple(
                median(
                    normalized[item.sample_id][position][channel]
                    for item in split.train
                )
                for channel in range(CHANNELS)
            )
            for position in range(CHALLENGE_LENGTH)
        )
        genuine = [
            distance(normalized[item.sample_id], prototype) for item in split.validation
        ]
        impostor = [
            distance(normalized[item.sample_id], prototype)
            for other_id, other_split in splits.items()
            if other_id != profile_id
            for item in other_split.validation
        ]
        threshold, calibration = calibrate_threshold(genuine, impostor)
        models[profile_id] = BaselineModel(
            profile_id,
            scaler,
            prototype,
            threshold,
            tuple(item.sample_id for item in split.train),
            tuple(item.sample_id for item in split.validation),
            calibration_sessions_disjoint,
            calibration,
        )
    return models


def score_sample(
    model: BaselineModel, sequence: TimingSequence | dict
) -> tuple[float, float, bool]:
    value = distance(
        normalize(extract_features(sequence), model.scaler), model.prototype
    )
    similarity = 1.0 / (1.0 + value)
    threshold = 1.0 / (1.0 + model.threshold_distance)
    return similarity, value, similarity > threshold
