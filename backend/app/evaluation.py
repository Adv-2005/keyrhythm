"""Known-user comparison on the Siamese artifact's untouched test partition.

Both verifiers use identical claims and recordings. Training rows fit the
scaler and references, validation rows choose thresholds, and test rows are
used only to produce the final metrics and the prespecified reference study.
"""

from dataclasses import asdict, dataclass
from itertools import pairwise
from math import isclose, isfinite
from statistics import median

import torch
from torch import Tensor
from torch.nn import functional as F

from app.baseline import (
    CHANNELS,
    FEATURE_MATRIX_VERSION,
    FeatureMatrix,
    Recording,
    calibrate_threshold,
    distance,
    extract_features,
    fit_scaler,
    normalize,
)
from app.baseline import MODEL_VERSION as BASELINE_VERSION
from app.database import SiameseArtifact
from app.schemas import CHALLENGE_LENGTH, CHALLENGE_VERSION, FEATURE_VERSION
from app.siamese import MODEL_VERSION as SIAMESE_VERSION
from app.siamese import RecordingSplit, tensor_for
from app.siamese_service import load_trained

PROTOCOL_VERSION = "known-user-test-v1"
MIN_CLASS_COUNT_FOR_AUC_EER = 20


@dataclass(frozen=True)
class Trial:
    claimed_profile_id: int
    recording_id: int
    genuine: bool
    similarity_score: float
    decision_threshold: float
    decision_margin: float
    accepted: bool


def restore_splits(
    recordings: list[Recording], manifest: dict
) -> dict[int, RecordingSplit]:
    """Audit IDs, profile ownership, partition isolation, and session claims."""
    by_id = {item.sample_id: item for item in recordings}
    if len(by_id) != len(recordings):
        raise ValueError("Duplicate sample IDs in dataset")
    if len(manifest) < 3:
        raise ValueError("At least three trained profiles are required")
    splits: dict[int, RecordingSplit] = {}
    assigned: set[int] = set()
    for raw_profile_id, parts in sorted(manifest.items(), key=lambda pair: int(pair[0])):
        profile_id = int(raw_profile_id)
        partitions = []
        for key in ("train_ids", "validation_ids", "test_ids"):
            ids = parts[key]
            if len(ids) != len(set(ids)) or any(
                sample_id in assigned or sample_id not in by_id
                or by_id[sample_id].profile_id != profile_id
                for sample_id in ids
            ):
                raise ValueError("Invalid or overlapping sample IDs in split manifest")
            assigned.update(ids)
            partitions.append(tuple(by_id[sample_id] for sample_id in ids))
        train, validation, test = partitions
        if len(train) < 4 or len(validation) < 2 or len(test) < 2:
            raise ValueError("Split has too few recordings")
        profile_ids = {
            item.sample_id for item in recordings if item.profile_id == profile_id
        }
        if profile_ids != {item.sample_id for part in partitions for item in part}:
            raise ValueError("Split manifest does not cover the current profile dataset")
        session_disjoint = parts["session_disjoint"]
        if not isinstance(session_disjoint, bool):
            raise TypeError("Invalid session split flag")
        if session_disjoint:
            groups = [{item.session_id for item in part} for part in partitions]
            if groups[0] & groups[1] or groups[0] & groups[2] or groups[1] & groups[2]:
                raise ValueError("Session leakage in split manifest")
        splits[profile_id] = RecordingSplit(
            train, validation, test, session_disjoint
        )
    return splits


def _roc_points(trials: list[Trial], genuine_count: int, impostor_count: int) -> list[dict]:
    # Profile thresholds differ, so pool score margins, not raw similarities.
    values = sorted({item.decision_margin for item in trials}, reverse=True)
    thresholds = [values[0]]
    thresholds.extend((left + right) / 2 for left, right in pairwise(values))
    thresholds.extend((0.0, values[-1] - 1e-9))
    thresholds = sorted(set(thresholds), reverse=True)
    return [
        {
            "decision_margin_threshold": threshold,
            "false_positive_rate": sum(
                item.decision_margin > threshold for item in trials if not item.genuine
            ) / impostor_count,
            "true_positive_rate": sum(
                item.decision_margin > threshold for item in trials if item.genuine
            ) / genuine_count,
        }
        for threshold in thresholds
    ]


def summarize_trials(trials: list[Trial]) -> tuple[dict, list[dict]]:
    genuine = [item for item in trials if item.genuine]
    impostor = [item for item in trials if not item.genuine]
    if not genuine or not impostor:
        raise ValueError("Both genuine and impostor test attempts are required")
    if any(
        not isfinite(item.similarity_score)
        or not isfinite(item.decision_threshold)
        or not isfinite(item.decision_margin)
        or not 0 < item.similarity_score <= 1
        or not 0 <= item.decision_threshold <= 1
        or not isclose(item.decision_margin, item.similarity_score - item.decision_threshold, abs_tol=1e-9)
        or item.accepted != (item.similarity_score > item.decision_threshold)
        for item in trials
    ):
        raise ValueError("Invalid test score or decision")
    tp = sum(item.accepted for item in genuine)
    fn = len(genuine) - tp
    fp = sum(item.accepted for item in impostor)
    tn = len(impostor) - fp
    points = _roc_points(trials, len(genuine), len(impostor))
    supported = (
        len(genuine) >= MIN_CLASS_COUNT_FOR_AUC_EER
        and len(impostor) >= MIN_CLASS_COUNT_FOR_AUC_EER
    )
    auc: float | None = None
    eer: float | None = None
    if supported:
        auc = sum(
            (right["false_positive_rate"] - left["false_positive_rate"])
            * (left["true_positive_rate"] + right["true_positive_rate"]) / 2
            for left, right in pairwise(points)
        )
        for left, right in pairwise(points):
            before = left["false_positive_rate"] + left["true_positive_rate"] - 1
            after = right["false_positive_rate"] + right["true_positive_rate"] - 1
            if before <= 0 <= after:
                fraction = 0.0 if before == after else -before / (after - before)
                eer = left["false_positive_rate"] + fraction * (
                    right["false_positive_rate"] - left["false_positive_rate"]
                )
                break
    return (
        {
            "genuine_count": len(genuine),
            "impostor_count": len(impostor),
            "true_positive": tp,
            "false_negative": fn,
            "false_positive": fp,
            "true_negative": tn,
            "false_acceptance_rate": fp / len(impostor),
            "false_rejection_rate": fn / len(genuine),
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / len(genuine),
            "roc_auc": auc,
            "equal_error_rate": eer,
            "auc_eer_supported": supported,
        },
        points,
    )


def _baseline_reference(
    training: tuple[Recording, ...], matrices: dict[int, FeatureMatrix]
) -> FeatureMatrix:
    return tuple(
        tuple(
            median(matrices[item.sample_id][position][channel] for item in training)
            for channel in range(CHANNELS)
        )
        for position in range(CHALLENGE_LENGTH)
    )


def _neural_reference(
    training: tuple[Recording, ...], embeddings: dict[int, Tensor]
) -> Tensor:
    return F.normalize(
        torch.stack([embeddings[item.sample_id] for item in training]).mean(0), dim=0
    )


def _measured_distance(
    model_type: str,
    item: Recording,
    reference: FeatureMatrix | Tensor,
    matrices: dict[int, FeatureMatrix],
    embeddings: dict[int, Tensor],
) -> float:
    if model_type == "baseline":
        return distance(matrices[item.sample_id], reference)
    return torch.dist(embeddings[item.sample_id], reference).item()


def _variant(
    splits: dict[int, RecordingSplit],
    matrices: dict[int, FeatureMatrix],
    embeddings: dict[int, Tensor],
    stored_profiles: dict,
    reference_count: int | None,
) -> dict:
    profile_ids = sorted(splits)
    thresholds: dict[str, dict[str, float]] = {"baseline": {}, "siamese": {}}
    calibration: dict[str, dict[str, dict]] = {"baseline": {}, "siamese": {}}
    references: dict[str, dict[int, FeatureMatrix | Tensor]] = {
        "baseline": {}, "siamese": {}
    }
    for profile_id in profile_ids:
        split = splits[profile_id]
        training = split.train[:reference_count] if reference_count else split.train
        baseline_ref = _baseline_reference(training, matrices)
        neural_ref = _neural_reference(training, embeddings)
        references["baseline"][profile_id] = baseline_ref
        references["siamese"][profile_id] = neural_ref
        if reference_count is None:
            saved = stored_profiles[str(profile_id)]
            saved_ref = torch.tensor(saved["centroid"], dtype=torch.float32)
            if not torch.allclose(neural_ref, saved_ref, atol=1e-6):
                raise ValueError("Saved neural reference does not match training split")
        for model_type in ("baseline", "siamese"):
            reference = references[model_type][profile_id]

            genuine = [
                _measured_distance(model_type, item, reference, matrices, embeddings)
                for item in split.validation
            ]
            impostor = [
                _measured_distance(model_type, item, reference, matrices, embeddings)
                for other_id in profile_ids if other_id != profile_id
                for item in splits[other_id].validation
            ]
            threshold_distance, rates = calibrate_threshold(genuine, impostor)
            if model_type == "siamese" and reference_count is None:
                saved_threshold = float(stored_profiles[str(profile_id)]["threshold_distance"])
                if not isclose(threshold_distance, saved_threshold, abs_tol=1e-5):
                    raise ValueError("Saved neural threshold does not match validation split")
                threshold_distance = saved_threshold
            thresholds[model_type][str(profile_id)] = 1 / (1 + threshold_distance)
            calibration[model_type][str(profile_id)] = {
                **asdict(rates),
                "session_disjoint": split.session_disjoint,
                "training_count": len(training),
                "validation_count": len(split.validation),
            }
    results = {}
    for model_type in ("baseline", "siamese"):
        trials = []
        for claimed_id in profile_ids:
            reference = references[model_type][claimed_id]
            threshold = thresholds[model_type][str(claimed_id)]
            for source_id in profile_ids:
                for item in splits[source_id].test:
                    measured_distance = _measured_distance(
                        model_type, item, reference, matrices, embeddings
                    )
                    score = 1 / (1 + measured_distance)
                    trials.append(Trial(
                        claimed_profile_id=claimed_id,
                        recording_id=item.sample_id,
                        genuine=claimed_id == source_id,
                        similarity_score=score,
                        decision_threshold=threshold,
                        decision_margin=score - threshold,
                        accepted=score > threshold,
                    ))
        metrics, roc = summarize_trials(trials)
        results[model_type] = {
            "metrics": metrics,
            "roc": roc,
            "thresholds": thresholds[model_type],
            "validation_calibration": calibration[model_type],
            "trials": [asdict(item) for item in trials],
        }
    baseline_keys = [
        (item["claimed_profile_id"], item["recording_id"], item["genuine"])
        for item in results["baseline"]["trials"]
    ]
    neural_keys = [
        (item["claimed_profile_id"], item["recording_id"], item["genuine"])
        for item in results["siamese"]["trials"]
    ]
    if baseline_keys != neural_keys:
        raise ValueError("Models were evaluated on different test attempts")
    return results


def evaluate_models(
    recordings: list[Recording], artifact: SiameseArtifact, fingerprint: str
) -> dict:
    """Compare both models using the neural artifact's saved held-out protocol."""
    if artifact.dataset_fingerprint != fingerprint or artifact.model_version != SIAMESE_VERSION:
        raise ValueError("Neural artifact is stale; retrain before evaluation")
    state = artifact.state
    if (state["model_version"] != SIAMESE_VERSION
        or state["feature_matrix_version"] != FEATURE_MATRIX_VERSION):
        raise ValueError("Unsupported neural artifact version")
    splits = restore_splits(recordings, state["splits"])
    if set(map(int, state["profiles"])) != set(splits):
        raise ValueError("Neural profiles and split manifest differ")
    training = [item for split in splits.values() for item in split.train]
    scaler = fit_scaler(training)
    network, stored_scaler, _ = load_trained(artifact, fingerprint, min(splits))
    if scaler != stored_scaler:
        raise ValueError("Stored neural scaler differs from training-only scaler")
    selected = [
        item for split in splits.values()
        for item in (*split.train, *split.validation, *split.test)
    ]
    matrices = {
        item.sample_id: normalize(extract_features(item.timing_sequence), scaler)
        for item in selected
    }
    with torch.no_grad():
        embeddings = {
            item.sample_id: network.encoder(
                tensor_for(item.timing_sequence, scaler).unsqueeze(0)
            ).squeeze(0)
            for item in selected
        }
    primary = _variant(splits, matrices, embeddings, state["profiles"], None)
    minimum_training = min(len(split.train) for split in splits.values())
    counts = [value for value in (2, 4, 8, 16, 32) if value < minimum_training]
    counts.append(minimum_training)
    reference_study = []
    for count in counts:
        variant = _variant(splits, matrices, embeddings, state["profiles"], count)
        reference_study.append({
            "reference_count": count,
            "baseline": variant["baseline"]["metrics"],
            "siamese": variant["siamese"]["metrics"],
        })
    test_count = sum(len(split.test) for split in splits.values())
    limitations = [
        "This is known-user verification on local fixed-challenge recordings; it does not measure unseen-user generalization or production security.",
        "The reference-count study changes stored profile references while keeping the trained encoder and scaler fixed; it is not a neural retraining ablation.",
    ]
    if any(not split.session_disjoint for split in splits.values()):
        limitations.append(
            "Some profiles lack session-disjoint partitions; session effects may inflate performance."
        )
    if not primary["baseline"]["metrics"]["auc_eer_supported"]:
        limitations.append(
            f"ROC-AUC and EER are omitted until each test class has at least {MIN_CLASS_COUNT_FOR_AUC_EER} attempts; the ROC curve is exploratory."
        )
    return {
        "protocol_version": PROTOCOL_VERSION,
        "dataset_fingerprint": fingerprint,
        "challenge_version": CHALLENGE_VERSION,
        "timing_feature_version": FEATURE_VERSION,
        "feature_matrix_version": FEATURE_MATRIX_VERSION,
        "model_versions": {"baseline": BASELINE_VERSION, "siamese": SIAMESE_VERSION},
        "training_configuration": state["config"],
        "training_history": state["history"],
        "best_epoch": state["best_epoch"],
        "torch_version": state["torch_version"],
        "split_configuration": state["splits"],
        "profile_count": len(splits),
        "sample_count": len(selected),
        "test_recording_count": test_count,
        "trial_count_per_model": len(primary["baseline"]["trials"]),
        "models": primary,
        "reference_count_effect": reference_study,
        "limitations": limitations,
    }
