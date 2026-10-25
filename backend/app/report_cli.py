"""Export aggregate tables and figures from an existing saved experiment.

Usage from backend/: python -m app.report_cli --output data/report-1
This command never trains a model or opens the held-out partition again.
"""

import argparse
import csv
import sys
from pathlib import Path

from sqlalchemy import select

from app.database import Base, Experiment, Profile, SessionLocal, engine
from app.schemas import ExperimentResult


def _number(value: float | None, digits: int = 4) -> str:
    if value is None:
        return "N/A"
    return str(value) if isinstance(value, int) else f"{value:.{digits}f}"


def _save_figure(figure, output: Path, name: str) -> None:
    for extension in ("svg", "png"):
        figure.savefig(output / f"{name}.{extension}", dpi=200, bbox_inches="tight")


def _figures(result: dict, output: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = {"baseline": "#4f46e5", "siamese": "#059669"}
    names = {"baseline": "Distance baseline", "siamese": "Siamese CNN"}
    fig, ax = plt.subplots(figsize=(6.4, 5.2))
    for model in ("baseline", "siamese"):
        data = result["models"][model]
        points = data["roc"]
        auc = data["metrics"]["roc_auc"]
        label = names[model] + (f" (AUC {auc:.3f})" if auc is not None else " (exploratory)")
        ax.step(
            [point["false_positive_rate"] for point in points],
            [point["true_positive_rate"] for point in points],
            where="post", label=label, color=colors[model], linewidth=2,
        )
    ax.plot([0, 1], [0, 1], color="#94a3b8", linestyle="--", linewidth=1)
    ax.set(xlabel="False positive rate", ylabel="True positive rate", xlim=(0, 1), ylim=(0, 1),
           title="Held-out known-user ROC")
    ax.grid(alpha=0.2)
    ax.legend(loc="lower right")
    _save_figure(fig, output, "roc")
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(8.8, 3.8), constrained_layout=True)
    for ax, model in zip(axes, ("baseline", "siamese"), strict=True):
        metrics = result["models"][model]["metrics"]
        matrix = [[metrics["true_positive"], metrics["false_negative"]],
                  [metrics["false_positive"], metrics["true_negative"]]]
        ax.imshow(matrix, cmap="Blues", vmin=0)
        for row in range(2):
            for column in range(2):
                ax.text(column, row, str(matrix[row][column]), ha="center", va="center", fontsize=15)
        ax.set_xticks((0, 1), ("Accept", "Reject"))
        ax.set_yticks((0, 1), ("Genuine", "Impostor"))
        ax.set(xlabel="Prediction", ylabel="Attempt class", title=names[model])
    _save_figure(fig, output, "confusion")
    plt.close(fig)

    history = result["training_history"]
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.plot([row["epoch"] for row in history], [row["train_loss"] for row in history],
            marker="o", color=colors["baseline"], label="Training")
    ax.plot([row["epoch"] for row in history], [row["validation_loss"] for row in history],
            marker="o", color="#e11d48", label="Validation")
    ax.set(xlabel="Epoch", ylabel="Contrastive loss", title="Siamese training history")
    ax.grid(alpha=0.2)
    ax.legend()
    _save_figure(fig, output, "training-loss")
    plt.close(fig)

    study = result["reference_count_effect"]
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    for model in ("baseline", "siamese"):
        for metric, linestyle in (("false_acceptance_rate", "-"), ("false_rejection_rate", "--")):
            ax.plot(
                [row["reference_count"] for row in study],
                [row[model][metric] for row in study],
                marker="o", linestyle=linestyle, color=colors[model],
                label=f"{names[model]} {'FAR' if metric == 'false_acceptance_rate' else 'FRR'}",
            )
    ax.set(xlabel="Training references per profile", ylabel="Held-out error rate",
           ylim=(0, 1), title="Effect of profile reference count")
    ax.grid(alpha=0.2)
    ax.legend(fontsize=8)
    _save_figure(fig, output, "reference-count")
    plt.close(fig)


def _tables(experiment: Experiment, result: dict, output: Path, source: str) -> None:
    metrics_columns = (
        "model", "genuine_count", "impostor_count", "true_positive", "false_negative",
        "false_positive", "true_negative", "false_acceptance_rate", "false_rejection_rate",
        "precision", "recall", "roc_auc", "equal_error_rate", "auc_eer_supported",
    )
    with (output / "metrics.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=metrics_columns)
        writer.writeheader()
        for model in ("baseline", "siamese"):
            writer.writerow({"model": model, **result["models"][model]["metrics"]})

    with (output / "reference-count.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(("references", "baseline_far", "baseline_frr", "siamese_far", "siamese_frr"))
        for row in result["reference_count_effect"]:
            writer.writerow((row["reference_count"],
                             row["baseline"]["false_acceptance_rate"],
                             row["baseline"]["false_rejection_rate"],
                             row["siamese"]["false_acceptance_rate"],
                             row["siamese"]["false_rejection_rate"]))

    lines = [
        f"# Saved experiment {experiment.id}", "",
        f"**Data source:** {source}",
        f"**Recorded:** {experiment.created_at.isoformat()}",
        f"**Protocol:** {result['protocol_version']}",
        f"**Dataset fingerprint:** `{result['dataset_fingerprint']}`", "",
        "## Held-out comparison", "",
        (f"{result['profile_count']} profiles, {result['sample_count']} included recordings, "
         f"{result['test_recording_count']} distinct test recordings, "
         f"{result['trial_count_per_model']} attempts per model."), "",
        "| Metric | Distance baseline | Siamese CNN |",
        "| --- | ---: | ---: |",
    ]
    for label, key in (
        ("Genuine attempts", "genuine_count"), ("Impostor attempts", "impostor_count"),
        ("True positives", "true_positive"), ("False negatives", "false_negative"),
        ("False positives", "false_positive"), ("True negatives", "true_negative"),
        ("FAR", "false_acceptance_rate"), ("FRR", "false_rejection_rate"),
        ("Precision", "precision"), ("Recall", "recall"),
        ("ROC-AUC", "roc_auc"), ("EER", "equal_error_rate"),
    ):
        baseline = result["models"]["baseline"]["metrics"][key]
        siamese = result["models"]["siamese"]["metrics"][key]
        lines.append(f"| {label} | {_number(baseline)} | {_number(siamese)} |")
    lines.extend(("", "AUC and EER appear as N/A when the test class counts do not meet the reporting gate.",
                  "", "## Experiment settings", "",
                  f"- Challenge: `{result['challenge_version']}`; timing: `{result['timing_feature_version']}`; feature matrix: `{result['feature_matrix_version']}`.",
                  f"- Baseline: `{result['model_versions']['baseline']}`; Siamese: `{result['model_versions']['siamese']}`.",
                  f"- Neural configuration: `{result['training_configuration']}`.",
                  f"- Best validation epoch: {result['best_epoch']}; PyTorch: `{result['torch_version']}`.",
                  f"- Code revision: `{result['code_revision']['commit']}`; dirty tree: {result['code_revision']['working_tree_dirty']}.",
                  "", "## Saved split sizes", "",
                  "| Profile ID | Train | Validation | Test | Sessions separate |",
                  "| --- | ---: | ---: | ---: | --- |"))
    for profile_id, split in sorted(result["split_configuration"].items(), key=lambda item: int(item[0])):
        lines.append(f"| {profile_id} | {len(split['train_ids'])} | {len(split['validation_ids'])} | {len(split['test_ids'])} | {'yes' if split['session_disjoint'] else 'no'} |")
    lines.extend(("", "## Figures", "",
                  "- [ROC curve](roc.svg)", "- [Confusion matrices](confusion.svg)",
                  "- [Training loss](training-loss.svg)",
                  "- [Reference count study](reference-count.svg)",
                  "", "## Limitations", ""))
    lines.extend(f"- {limitation}" for limitation in result["limitations"])
    lines.append("")
    (output / "results.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment-id", type=int, help="Saved run ID (default: latest)")
    parser.add_argument("--output", type=Path, required=True, help="New empty output directory")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        print(f"Output directory is not empty: {output}", file=sys.stderr)
        return 1
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        experiment = (db.get(Experiment, args.experiment_id) if args.experiment_id is not None
                      else db.scalars(select(Experiment).order_by(Experiment.id.desc())).first())
        if experiment is None:
            print("No saved experiment found; train and evaluate first", file=sys.stderr)
            return 1
        result = ExperimentResult.model_validate(experiment.state).model_dump()
        names = list(db.scalars(select(Profile.display_name)))
        source = ("SYNTHETIC SOFTWARE DEMO — not participant evidence"
                  if names and all(name.startswith("SYNTHETIC ") for name in names)
                  else "Local dataset — participant provenance must be verified separately")
        output.mkdir(parents=True, exist_ok=True)
        _tables(experiment, result, output, source)
        _figures(result, output)
    print(f"Exported saved experiment {experiment.id} to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
