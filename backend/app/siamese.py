"""Small, CPU-based Siamese verifier over the baseline's timing representation.

All partitions contain original recordings. Scaling is fitted on training data,
pairs are made within a partition, and thresholds use validation data only.
The test partition is recorded for Milestone 5 and never read during fitting.
"""

from dataclasses import dataclass
from itertools import combinations
from math import isfinite
from random import Random

import torch
from torch import Tensor, nn
from torch.nn import functional as F

from app.baseline import (
    FEATURE_MATRIX_VERSION,
    ErrorRates,
    InsufficientDataError,
    Recording,
    Scaler,
    calibrate_threshold,
    extract_features,
    fit_scaler,
    normalize,
)
from app.schemas import (
    SIAMESE_MIN_PROFILES,
    SIAMESE_MIN_SAMPLES_PER_PROFILE,
    SIAMESE_MODEL_VERSION,
    TimingSequence,
)

MODEL_VERSION = SIAMESE_MODEL_VERSION
MIN_PROFILES = SIAMESE_MIN_PROFILES
MIN_SAMPLES_PER_PROFILE = SIAMESE_MIN_SAMPLES_PER_PROFILE
CHANNELS = 3


@dataclass(frozen=True)
class TrainingConfig:
    epochs: int = 20
    batch_size: int = 32
    learning_rate: float = 0.001
    embedding_dim: int = 32
    margin: float = 1.0
    seed: int = 42


@dataclass(frozen=True)
class RecordingSplit:
    train: tuple[Recording, ...]
    validation: tuple[Recording, ...]
    test: tuple[Recording, ...]
    session_disjoint: bool


@dataclass(frozen=True)
class Pair:
    left_id: int
    right_id: int
    same_profile: bool


@dataclass(frozen=True)
class ProfileCalibration:
    centroid: tuple[float, ...]
    threshold_distance: float
    rates: ErrorRates


@dataclass(frozen=True)
class TrainingResult:
    config: TrainingConfig
    scaler: Scaler
    splits: dict[int, RecordingSplit]
    profiles: dict[int, ProfileCalibration]
    history: tuple[dict[str, float], ...]
    best_epoch: int
    state_dict: dict[str, Tensor]

    def metadata(self) -> dict:
        return {
            "model_version": MODEL_VERSION,
            "feature_matrix_version": FEATURE_MATRIX_VERSION,
            "torch_version": torch.__version__,
            "config": self.config.__dict__,
            "scaler": self.scaler.__dict__,
            "splits": {
                str(profile_id): {
                    "train_ids": [item.sample_id for item in split.train],
                    "validation_ids": [item.sample_id for item in split.validation],
                    "test_ids": [item.sample_id for item in split.test],
                    "session_disjoint": split.session_disjoint,
                }
                for profile_id, split in self.splits.items()
            },
            "profiles": {
                str(profile_id): {
                    "centroid": profile.centroid,
                    "threshold_distance": profile.threshold_distance,
                    "calibration": profile.rates.__dict__,
                }
                for profile_id, profile in self.profiles.items()
            },
            "history": self.history,
            "best_epoch": self.best_epoch,
        }


class TrainingError(RuntimeError):
    pass


class Encoder(nn.Module):
    def __init__(self, embedding_dim: int = 32) -> None:
        super().__init__()
        self.layers = nn.Sequential(
            nn.Conv1d(CHANNELS, 16, kernel_size=5, padding=2),
            nn.ReLU(),
            nn.Conv1d(16, 32, kernel_size=5, padding=2),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(4),
            nn.Flatten(),
            nn.Linear(128, embedding_dim),
        )

    def forward(self, values: Tensor) -> Tensor:
        return F.normalize(self.layers(values), dim=1)


class SiameseNetwork(nn.Module):
    """Both inputs pass through the same encoder instance."""

    def __init__(self, embedding_dim: int = 32) -> None:
        super().__init__()
        self.encoder = Encoder(embedding_dim)

    def forward(self, left: Tensor, right: Tensor) -> tuple[Tensor, Tensor]:
        return self.encoder(left), self.encoder(right)


def contrastive_loss(
    left: Tensor, right: Tensor, same_profile: Tensor, margin: float
) -> Tensor:
    distances = F.pairwise_distance(left, right)
    return (
        same_profile * distances.square()
        + (1 - same_profile) * F.relu(margin - distances).square()
    ).mean()


def split_recordings(recordings: list[Recording]) -> RecordingSplit:
    ordered = sorted(recordings, key=lambda item: item.sample_id)
    if len(ordered) < MIN_SAMPLES_PER_PROFILE:
        raise InsufficientDataError(
            f"At least {MIN_SAMPLES_PER_PROFILE} recordings per profile are required"
        )
    sessions = list(dict.fromkeys(item.session_id for item in ordered))
    if len(sessions) >= 3:
        test = tuple(item for item in ordered if item.session_id == sessions[-1])
        validation = tuple(
            item for item in ordered if item.session_id == sessions[-2]
        )
        train = tuple(
            item
            for item in ordered
            if item.session_id not in (sessions[-1], sessions[-2])
        )
        if len(train) >= 4 and len(validation) >= 2 and len(test) >= 2:
            return RecordingSplit(train, validation, test, True)
    return RecordingSplit(
        tuple(ordered[:-4]), tuple(ordered[-4:-2]), tuple(ordered[-2:]), False
    )


def prepare_splits(recordings: list[Recording]) -> dict[int, RecordingSplit]:
    ids = [item.sample_id for item in recordings]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate recording IDs")
    by_profile: dict[int, list[Recording]] = {}
    for item in recordings:
        by_profile.setdefault(item.profile_id, []).append(item)
    splits = {
        profile_id: split_recordings(items)
        for profile_id, items in sorted(by_profile.items())
        if len(items) >= MIN_SAMPLES_PER_PROFILE
    }
    if len(splits) < MIN_PROFILES:
        raise InsufficientDataError(
            f"At least {MIN_PROFILES} profiles with {MIN_SAMPLES_PER_PROFILE} "
            "samples each are required for neural training"
        )
    for split in splits.values():
        train_ids = {item.sample_id for item in split.train}
        validation_ids = {item.sample_id for item in split.validation}
        test_ids = {item.sample_id for item in split.test}
        if train_ids & validation_ids or train_ids & test_ids or validation_ids & test_ids:
            raise ValueError("Recording leakage across partitions")
        if split.session_disjoint:
            session_sets = [
                {item.session_id for item in partition}
                for partition in (split.train, split.validation, split.test)
            ]
            if any(
                session_sets[i] & session_sets[j]
                for i, j in ((0, 1), (0, 2), (1, 2))
            ):
                raise ValueError("Session leakage across partitions")
    return splits


def make_pairs(recordings: list[Recording], seed: int) -> tuple[Pair, ...]:
    by_profile: dict[int, list[int]] = {}
    for item in recordings:
        by_profile.setdefault(item.profile_id, []).append(item.sample_id)
    positives = [
        Pair(left, right, True)
        for ids in by_profile.values()
        for left, right in combinations(sorted(ids), 2)
    ]
    negatives = [
        Pair(left, right, False)
        for first, second in combinations(sorted(by_profile), 2)
        for left in sorted(by_profile[first])
        for right in sorted(by_profile[second])
    ]
    if not positives or not negatives:
        raise InsufficientDataError("Both positive and negative pairs are required")
    rng = Random(seed)
    count = min(len(positives), len(negatives), 2000)
    return tuple(
        rng.sample(positives, count) + rng.sample(negatives, count)
    )


def tensor_for(sequence: TimingSequence, scaler: Scaler) -> Tensor:
    matrix = normalize(extract_features(sequence), scaler)
    # One documented clipping step is shared by training and inference.
    return torch.tensor(matrix, dtype=torch.float32).clamp(-10, 10).T.contiguous()


def _pair_loss(
    network: SiameseNetwork,
    pairs: tuple[Pair, ...],
    tensors: dict[int, Tensor],
    margin: float,
    batch_size: int,
    optimizer: torch.optim.Optimizer | None = None,
) -> float:
    losses = []
    for start in range(0, len(pairs), batch_size):
        batch = pairs[start : start + batch_size]
        left = torch.stack([tensors[pair.left_id] for pair in batch])
        right = torch.stack([tensors[pair.right_id] for pair in batch])
        labels = torch.tensor(
            [float(pair.same_profile) for pair in batch], dtype=torch.float32
        )
        if optimizer is not None:
            optimizer.zero_grad()
        embeddings = network(left, right)
        loss = contrastive_loss(*embeddings, labels, margin)
        if not torch.isfinite(loss):
            raise TrainingError("Training produced a non-finite loss")
        if optimizer is not None:
            loss.backward()
            optimizer.step()
        losses.append((loss.item(), len(batch)))
    return sum(value * count for value, count in losses) / len(pairs)


def train(recordings: list[Recording], config: TrainingConfig) -> TrainingResult:
    splits = prepare_splits(recordings)
    training = [item for split in splits.values() for item in split.train]
    validation = [item for split in splits.values() for item in split.validation]
    scaler = fit_scaler(training)
    tensors = {
        item.sample_id: tensor_for(item.timing_sequence, scaler)
        for item in (*training, *validation)
    }
    train_pairs = make_pairs(training, config.seed)
    validation_pairs = make_pairs(validation, config.seed)
    torch.manual_seed(config.seed)
    network = SiameseNetwork(config.embedding_dim)
    optimizer = torch.optim.Adam(network.parameters(), lr=config.learning_rate)
    rng = Random(config.seed)
    history: list[dict[str, float]] = []
    best_loss = float("inf")
    best_epoch = 0
    best_state: dict[str, Tensor] | None = None
    for epoch in range(1, config.epochs + 1):
        shuffled = list(train_pairs)
        rng.shuffle(shuffled)
        network.train()
        train_loss = _pair_loss(
            network, tuple(shuffled), tensors, config.margin, config.batch_size,
            optimizer,
        )
        network.eval()
        with torch.no_grad():
            validation_loss = _pair_loss(
                network, validation_pairs, tensors, config.margin, config.batch_size
            )
        history.append({
            "epoch": float(epoch),
            "train_loss": train_loss,
            "validation_loss": validation_loss,
        })
        if validation_loss < best_loss:
            best_loss = validation_loss
            best_epoch = epoch
            best_state = {
                key: value.detach().clone()
                for key, value in network.state_dict().items()
            }
    if best_state is None:
        raise TrainingError("Training did not produce a valid checkpoint")
    network.load_state_dict(best_state)
    network.eval()
    with torch.no_grad():
        embeddings = {
            sample_id: network.encoder(value.unsqueeze(0)).squeeze(0)
            for sample_id, value in tensors.items()
        }
        profiles = {}
        for profile_id, split in splits.items():
            centroid = F.normalize(
                torch.stack([embeddings[item.sample_id] for item in split.train]).mean(0),
                dim=0,
            )
            genuine = [
                torch.dist(embeddings[item.sample_id], centroid).item()
                for item in split.validation
            ]
            impostor = [
                torch.dist(embeddings[item.sample_id], centroid).item()
                for other_id, other_split in splits.items()
                if other_id != profile_id
                for item in other_split.validation
            ]
            threshold, rates = calibrate_threshold(genuine, impostor)
            profiles[profile_id] = ProfileCalibration(
                tuple(centroid.tolist()), threshold, rates
            )
    return TrainingResult(
        config, scaler, splits, profiles, tuple(history), best_epoch, best_state
    )


def score_sample(
    network: SiameseNetwork,
    scaler: Scaler,
    profile: ProfileCalibration,
    sequence: TimingSequence,
) -> tuple[float, float, float, bool]:
    network.eval()
    with torch.no_grad():
        embedding = network.encoder(tensor_for(sequence, scaler).unsqueeze(0)).squeeze(0)
        centroid = torch.tensor(profile.centroid, dtype=torch.float32)
        distance = torch.dist(embedding, centroid).item()
    if not isfinite(distance):
        raise ValueError("Non-finite neural distance")
    similarity = 1.0 / (1.0 + distance)
    threshold = 1.0 / (1.0 + profile.threshold_distance)
    return similarity, distance, threshold, similarity > threshold
