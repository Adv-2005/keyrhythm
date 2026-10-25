# KeyRhythm: final report draft

**Status: participant results pending.** Milestone 7 verifies that the local software and reporting path work. No consented participant dataset is present in this repository or the inspected local database. Synthetic demo output is deliberately excluded from the empirical results below.

## Research question and method

The question is whether a small Siamese convolutional verifier improves known-user keystroke verification over a robust distance baseline on the same fixed challenge. An improvement is a hypothesis, **not an observed result**. The application captures timing only, enrols consenting profiles, fits both verifiers, and compares them on identical held-out attempts. The [architecture](architecture.md) gives the complete computation and data lifecycle; the [product requirements](../plan.md) define scope.

The protocol separates original recordings before fitting transforms or forming pairs. Training fits the scaler and references. Validation chooses the neural checkpoint and each model's profile thresholds. A held-out test partition supplies the final comparison once. Sessions are separated when collection volume permits and split IDs are audited on evaluation. Both models' scores increase as candidates get closer to a claimed profile. FAR = accepted impostor attempts / impostor attempts; FRR = rejected genuine attempts / genuine attempts. The study is known-user verification, not recognition of unseen participants.

## Results table

| Measure | Distance baseline | Siamese CNN | Interpretation |
| --- | ---: | ---: | --- |
| Profiles and included recordings | Pending | Same cohort | Requires consented participants |
| Held-out genuine / impostor attempts | Pending | Same attempts | Denominators must be reported |
| FAR | Pending | Pending | Lower is better |
| FRR | Pending | Pending | Lower is better |
| Precision / recall | Pending | Pending | Claim distribution dependent |
| ROC-AUC / EER | Pending | Pending | Suppressed if either test class has fewer than 20 attempts |
| Validation loss / selected epoch | N/A | Pending | Diagnostic for training, not test accuracy |
| Reference-count study | Pending | Pending | Fixed encoder/scaler; varies profile references only |

**Figures pending participant data:** held-out ROC, confusion matrices, Siamese training and validation loss, and reference-count FAR/FRR. `app.report_cli` writes these as SVG and PNG alongside `metrics.csv`, `reference-count.csv`, and a saved-run Markdown table after a real experiment exists. A zero-participant table must not be filled with the generated synthetic demonstration metrics.

## Reproducibility and provenance

Install with the [README](../README.md), collect the agreed participant dataset, train the Siamese model, and run evaluation once. Save the experiment ID, Git commit, dirty-tree flag, data and evaluation-code fingerprints, challenge/feature/model versions, Python/PyTorch versions, training configuration, seed, split manifest, and session-disjoint flags. Export with:

```powershell
Push-Location backend
$experimentId = 1 # Replace with the saved real experiment ID.
..\.venv\Scripts\python.exe -m app.report_cli --experiment-id $experimentId --output "data\report-$experimentId"
Pop-Location
```

The report export reads the saved experiment and does not retrain or re-evaluate test recordings. Keep the SQLite database and neural checkpoint together to reproduce the model's saved decisions. Store a controlled copy of the participant data only under an approved retention arrangement; the repository ignores local databases and checkpoints. Code and package versions alone cannot recreate results without the original consented dataset.

## Limitations

1. There is no participant dataset yet. Passing synthetic and automated tests shows pipeline behavior, not biometric accuracy, population generalization, or resistance to impostors.
2. Ten enrolment recordings per profile and three profiles are software minimums. They do not establish dataset sufficiency, error uncertainty, device diversity, or demographic coverage. The AUC/EER class-count gate is a reporting safeguard, not a power analysis.
3. The fixed sentence, desktop keyboard, browser event timing, operating system scheduling, and typing conditions may affect measurements. The server cannot independently verify typed text from timing-only payloads.
4. When session-disjoint splitting is infeasible, recording splits may share a participant's session across partitions. Known-user tests cannot estimate performance on unseen people or devices.
5. Validation tuning and repeated design choices can bias later test results. The held-out partition must remain sealed until the final prespecified comparison; revising the model after seeing test results needs a new independent dataset.
6. The prototype has no login, encryption at rest, or consent-management service. It is intended for local controlled research, not production authentication. Timing sequences remain identifiable biometric material; profile deletion does not delete external backups, screenshots, or exports.
7. Exact weight reproduction may vary across hardware, libraries, and execution backends even with seeds. The current verified path is local CPU with the pinned setup.

## Future work

With ethics and consent arrangements in place, collect a larger balanced cohort over multiple sessions and devices, record exclusions and participant-level uncertainty, and prespecify thresholds and comparisons. Add a user-grouped, unseen-participant evaluation using an independent test cohort. Evaluate browser and keyboard timing stability, missing or noisy events, and attack conditions. Add data retention tooling and storage encryption if the project moves beyond a local controlled prototype. Optional public benchmark adapters and model ablations belong to Milestone 8, after this report receives genuine measurements.
