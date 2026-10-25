# Implementation plan

## Starting point and assumptions

Inspection on 25 October 2026 found only `plan.md`; no application, dependency files, tests, hidden project files, or `.git` directory existed. This is a new project; Git was initialized during Milestone 0. The PRD is the source of truth. The first deployment target is a local single-machine research demo, not an identity-security product. Python 3.11 and Node.js 24 are available locally. Milestone 2 uses one versioned, lowercase ASCII challenge; see the README for the exact sentence and timing schema.

The working structure is one React frontend and one FastAPI backend. In the backend, keep routes and request schemas near each other, persistence in a small data module, and feature extraction, baseline, Siamese training, and evaluation as plain Python modules independent of HTTP. Add subpackages only when code volume warrants them. SQLite stores profile metadata and numeric timing sequences; generated model files stay outside version control. A single `frontend/src` tree can hold pages, a challenge component, API calls, and timing capture without adding a router or state library until needed.

## Milestone gates and dependencies

| Milestone | Depends on | Deliverable and gate |
| --- | --- | --- |
| **0. Inspection and plan** | PRD | Repository inventory, dependency declarations, ignore rules, environment examples, setup instructions, and this plan. No feature code. |
| **1. Application foundation** | 0 | Startable Vite/React UI and FastAPI API; `/api/v1/health`, local API connection, basic navigation and tests. Commit a tested frontend lockfile and record tested Python versions. |
| **2. Capture and enrolment** | 1 | Consent, profiles, fixed challenge, field-scoped timing capture, server validation, SQLite storage, deletion, and tests. No training dependency. |
| **3. Features and baseline** | 2 plus enough valid samples | Versioned preprocessing, distance-based baseline, validation-only threshold, actual inference and initial metrics. Capture schema must be stable before model fitting. |
| **4. Siamese model** | 3 plus sufficient multi-participant data | Split recordings first, construct pairs within partitions, train/load a small shared encoder, calibrate on validation, and test shapes, labels, and leakage. Report insufficiency if data is too small. |
| **5. Evaluation** | 3 and 4 | Compare both models on the same held-out protocol. Save seeds, sample/session identifiers, splits, versions, thresholds, denominators, and supported metrics/plots. |
| **6. Dashboard** | 2–5 | Complete UI flows using live API results, including model status, experiments, empty/error states, and actual charts. |
| **7. Final QA and report** | 1–6 | Fresh-install check, full tests, deletion/privacy audit, reproducible experiment, report, and demo walkthrough. |
| **8. Optional benchmark** | 7 | Only if time and licensing permit: benchmark adapter, subject-independent experiments, and ablations. |

The baseline and Siamese models must use identical test recordings and a documented score direction. Separate known-user verification from evaluation on unseen participants; they answer different questions. Authentication scores are similarities or distances, not calibrated probabilities.

Milestone 3 implements a standard-library distance baseline with versioned 44 × 3 features and validation-only threshold calibration. Artifacts and training/validation sample IDs are stored in SQLite. A dataset fingerprint invalidates artifacts when collection changes. The current FAR and FRR are calibration diagnostics on validation recordings; final held-out evaluation belongs to Milestone 5. The baseline accepts a minimal two-profile, six-sample-per-profile dataset for a functional demo, with session-disjoint validation when feasible. This minimum does not establish population-level accuracy.

## Decisions required before data collection and evaluation

1. **Timing schema:** `fixed-1` and `timing-1` use monotonic browser event timestamps in milliseconds, with holds aligned to 44 challenge positions and intervals aligned to adjacent positions. The browser rejects auto-repeat, composition/IME, paste, focus loss during typing, corrections, and missing key-up events. Browser and keyboard timing variation still needs a participant/device study. No global keyboard listener.
2. **Validation trust boundary:** the browser can check the typed challenge, but a timing-only payload does not let the server independently prove which text was entered. The server can validate shape, finite nonnegative values, plausible bounds, and versions. For a local research demo, document this limitation; do not present it as resistance to a malicious client.
3. **Privacy:** obtain explicit participant consent, use pseudonymous display labels, avoid text/key values in payloads, logs, database, or test fixtures, and define deletion of samples, trials, and derived artifacts linked to a profile. A display label alone does not make timing data anonymous. Review backups/exports before collecting real data.
4. **Dataset sufficiency:** the PRD's ten enrolment samples is a UI target, not enough evidence for a neural model. Aim for at least ten consenting participants with roughly 20–30 valid samples each if practical, across sessions. Check class balance, session effects, and uncertainty; suppress unsupported EER/AUC claims and distinguish a working demo from credible generalisation.
5. **Leakage control:** assign stable recording and session IDs. Partition original samples before normalization fitting, pair generation, augmentation, threshold selection, or hyperparameter search. Keep all derivatives of a recording in one partition. Fit transforms on training only; calibrate on validation only; open the held-out test once for final reporting. For unseen-user experiments, split users as groups too. Save split manifests and audit intersections.
6. **Reproducibility:** record dependency versions, random seeds, feature/challenge versions, dataset snapshot, model configuration, and code revision for every experiment. PyTorch CPU support is sufficient initially; GPU is optional.

## Dependency rationale

- React, TypeScript, Vite, Tailwind CSS, and Recharts match the PRD's UI stack. The Vite React and Tailwind plugins connect those libraries to the build tool. Vitest, Testing Library, jsdom, and React type packages support frontend tests and TypeScript.
- FastAPI, Pydantic, SQLAlchemy, SQLite, and Uvicorn provide the small local HTTP and storage stack. `pytest` and Ruff support tests and linting.
- NumPy and pandas handle numeric/experimental data; scikit-learn provides the baseline and metrics; PyTorch provides the Siamese model; Matplotlib is for exportable research plots. These ML packages are separate from the API requirements to keep foundation setup lighter.
- No router, global state manager, task queue, migration framework, authentication service, or cloud service is planned until a concrete requirement calls for one.

## Milestone 0 verification

Check the manifests and documentation with `Get-Content`; confirm ignored paths with `git check-ignore` after initializing Git; install dependency sets in fresh local environments when package registries are available. Startup, training, inference, and test commands are intentionally absent until their milestones create runnable code.
