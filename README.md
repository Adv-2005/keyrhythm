# KeyRhythm

KeyRhythm is a local research application for studying continuous user verification from keystroke timing. The [product requirements](plan.md) and [implementation plan](docs/implementation-plan.md) define the milestone scope.

**Current status: Milestone 5.** Profiles, consented typing capture, local SQLite storage, baseline and Siamese verification, and saved held-out model comparisons are available. The complete dashboard and final academic deliverables remain for later milestones.

## Requirements

- Python 3.11 (tested with 3.11.9 on Windows).
- Node.js 24 (tested with 24.12.0) and npm.
- Git.

## Install

From the repository root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.lock
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-ml.txt
npm.cmd --prefix frontend ci
```

The lockfiles capture the tested API and frontend dependency set. `backend/requirements.txt` and `backend/requirements-dev.txt` contain broader ranges for future updates. The baseline uses the API dependencies and Python's standard library. `backend/requirements-ml.txt` provides PyTorch and the declared research analysis packages. Neural runs record the installed PyTorch version with their configuration. In PowerShell on this machine, `npm.cmd` works where the `npm.ps1` shim is blocked by execution policy.

## Run locally

Start the backend in one PowerShell terminal from the repository root:

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Start the frontend in another terminal from the repository root:

```powershell
npm.cmd --prefix frontend run dev
```

Open `http://127.0.0.1:5173`. The status badge requests `/api/v1/health` through Vite's local proxy, which forwards to FastAPI at `http://127.0.0.1:8000`. `frontend/.env.example` documents the default browser API path; copying it to `.env` is optional. The backend creates `backend/data/keyrhythm.sqlite3` by default. To change the path or sample target, set `KEYRHYTHM_DATABASE_URL` and `KEYRHYTHM_ENROLLMENT_TARGET` in the backend process environment before starting Uvicorn. The values in `backend/.env.example` are examples and are not loaded automatically.

To check both servers:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health
Invoke-RestMethod http://127.0.0.1:5173/api/v1/health
```

Both commands should return `status: ok`, and the dashboard should display `API connected`.

## Tests and build

From the repository root:

```powershell
npm.cmd --prefix frontend run build
npm.cmd --prefix frontend test
Push-Location backend
..\.venv\Scripts\python.exe -m pytest -q
..\.venv\Scripts\python.exe -m ruff check app tests
Pop-Location
```

The frontend build includes TypeScript checking. Tests cover profile and sample lifecycle, invalid timing data, text privacy, browser capture and consent, recording splits, pair labels, shared encoder shapes, repeatable neural training, checkpoint loading, model staleness, held-out trial parity, metric denominators, and live result display. Neural and evaluation tests are skipped if PyTorch is not installed.

## Layout and data policy

```text
frontend/src/                 Dashboard, enrolment, verification, shared capture, API client
frontend/vite.config.ts       React, Tailwind, tests, and local API proxy
frontend/package-lock.json    Tested npm dependency graph
backend/app/main.py           FastAPI health, profile, sample, and model routes
backend/app/schemas.py        Versioned timing validation and API models
backend/app/database.py       SQLite profile and sample models
backend/app/baseline.py       Feature extraction, robust scaling, calibration, inference
backend/app/baseline_service.py SQLite snapshot and dataset fingerprint
backend/app/siamese.py        Shared CNN, pair construction, training, calibration, inference
backend/app/siamese_service.py Checkpoint storage and loading
frontend/src/ModelLaboratory.tsx Neural training controls and validation history
frontend/src/Evaluation.tsx Evaluation results, comparison, and plot downloads
backend/app/evaluation.py     Split audit, held-out trials, metrics, reference-count study
backend/app/evaluation_service.py Saved experiment lifecycle and code revision
backend/app/evaluation_plots.py SVG plots from saved results
backend/app/evaluate_cli.py   Repeatable local experiment command
backend/tests/                Backend tests
backend/requirements-dev.lock Tested Python API/test dependencies
docs/implementation-plan.md   Milestone gates and research risks
```

The initial version is an academic prototype, not an identity-security product. Timing capture runs only in the designated challenge field after consent. Raw keyboard events and entered challenge text stay transient in the browser; only numeric timing sequences and pseudonymous profile labels are sent. Local databases, generated model artifacts, and environment files are excluded by `.gitignore`.

## Enrolment and timing format

Create a profile, select it, accept the consent notice, and type the displayed sentence exactly. Corrections, paste, composition input, focus loss, repeated keys, and incomplete key releases require a sample restart. The collection target defaults to 10 samples per profile and is configurable through `KEYRHYTHM_ENROLLMENT_TARGET`; this is a UI collection target, not a claim of dataset sufficiency. Deleting a profile deletes its samples and derived experiment records. There are no automatic database backups or raw timing exports; if you copy the SQLite file or download a plot, manage and delete that copy separately.

The fixed challenge is `the quick brown fox jumps over the lazy dog.` (`fixed-1`, 44 positions). `timing-1` uses monotonic browser event timestamps in **milliseconds**. For each challenge position, `hold_ms[i]` is key-up minus key-down. For positions 1 through 43, `down_down_ms[i]` is the next key-down minus the current key-down; `flight_ms[i]` is the next key-down minus the current key-up, so negative values represent overlapping holds. `long_pauses[i]` is true when `flight_ms[i] >= 750`. `total_ms` is the final key-up minus the first key-down. Arrays are JSON numeric lists stored in SQLite with their challenge and feature versions, a random session ID, and a sample ID. List APIs return metadata and counts, never the timing arrays.

The backend checks versions, array lengths, finite numeric values, plausible bounds, and timing arithmetic. It cannot independently prove which text a browser user typed from a timing-only payload; the browser checks completion, and this local research API assumes an honest client. Browser timer precision and keyboard behavior can vary. The sample target should be revisited before model experiments, with multiple consenting participants and sessions and leakage-safe recording splits.

## Baseline verification

Collect at least **six valid samples for each of two profiles**, then open **Authentication** and choose **Train baseline**. The six-sample minimum is a software gate for fitting and calibration; the 10-sample enrolment target remains the default collection goal. More participants and sessions are needed for a credible study. Training fits all eligible profiles together and stores one baseline artifact per profile in the same local SQLite database. Adding or deleting a sample makes the artifacts stale; train again before verification. Deleting a profile also deletes its artifact. A fresh verification sample is processed for inference and is not saved.

`baseline-features-v1` is a 44 × 3 matrix. Each challenge position has key hold duration, key-down-to-key-down interval, and a long-pause flag. The final position has zero interval and pause padding. The scaler uses the median and median absolute deviation of **training recordings only**, with scale floors of 20 ms for holds and 30 ms for intervals. Each profile prototype is the position-wise median of its normalized training recordings. Verification uses the root-mean-square distance to that prototype. The displayed similarity is `1 / (1 + distance)` and is **not a probability**; larger values indicate a closer match.

For each eligible profile, validation reserves at least two original recordings. It separates entire collection sessions when enough training and validation recordings remain, and otherwise splits by recording ID. The threshold minimizes the average of false acceptance and false rejection on genuine and other-profile **validation** recordings; ties favor fewer false acceptances. A sample is accepted only when its similarity is strictly greater than the threshold. The API returns validation calibration rates and counts as preliminary diagnostics. These rates are not a held-out performance estimate. The final comparison fits a separate baseline on the neural model's saved training split.

The baseline API endpoints are `POST /api/v1/models/train`, `GET /api/v1/models/status`, and `POST /api/v1/authenticate`. The UI calls them directly. Training returns a conflict response until the minimum data requirement is met. Authentication returns a similarity score, threshold, decision, model version, and calibration context; it returns a conflict response when enrollment has changed since training.

## Siamese training and verification

Collect at least **10 valid recordings from each of three consenting profiles** before neural training. This is a functional software minimum, not evidence of reliable biometric accuracy. There is no collected participant dataset in this repository. The Model laboratory shows eligibility, accepts an epoch count and embedding size, and starts a synchronous local CPU run. The request remains busy until training and checkpoint saving finish. A failed run returns an error and does not replace the previous checkpoint.

The `siamese-cnn-v1` encoder uses two shared one-dimensional convolution layers, temporal pooling, and a configurable embedding projection (32 dimensions by default). Training uses balanced positive and negative recording pairs with contrastive loss. Both models use the same 44 × 3 `baseline-features-v1` timing matrix. A robust scaler is fitted on neural training recordings only; normalized inputs are clipped to [-10, 10] in both training and inference. Embeddings have unit length. The stored profile reference is the normalized mean of its training embeddings. Euclidean embedding distance is converted to similarity as `1 / (1 + distance)`. This score is not a probability.

Each eligible profile reserves original recordings for training, validation, and a held-out test partition **before** any scaling or pair construction. When at least three collection sessions have enough recordings, entire sessions are separated; otherwise, the split is by recording ID and the UI reports possible session overlap. Positive and negative pairs are formed within training or validation only. The best checkpoint is chosen by validation pair loss. Profile thresholds minimize balanced validation error using validation genuine and impostor samples. Held-out recordings are neither embedded nor scored during training; evaluation uses them for the final comparison. The artifact stores sample ID splits, seed, architecture and training settings, loss history, PyTorch version, feature version, and dataset fingerprint. Adding a sample makes the model stale. Deleting any profile removes the global neural checkpoint because its weights may contain information derived from that profile.

The neural endpoints are `POST /api/v1/models/siamese/train` and `GET /api/v1/models/siamese/status`. The training request accepts `epochs`, `batch_size`, `learning_rate`, `embedding_dim`, `margin`, and `seed`; omitted values use documented defaults in the API schema. To verify with the neural model, use Authentication → Siamese CNN or set `model_type: "siamese"` in `POST /api/v1/authenticate`. The response includes the actual embedding similarity, validation threshold, decision, and calibration counts. The status endpoint identifies missing data, an untrained model, a stale artifact, or a ready checkpoint. The laboratory's FAR and FRR are **validation calibration diagnostics**, not held-out performance estimates. More participants and sessions are needed before making research claims about generalization.

## Held-out evaluation

After collecting enough samples, train the Siamese model in **Model laboratory** or use explicit settings while the backend is running:

```powershell
$training = @{ epochs = 20; batch_size = 32; learning_rate = 0.001; embedding_dim = 32; margin = 1.0; seed = 42 } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/models/siamese/train -ContentType application/json -Body $training
```

Open **Evaluation** and choose **Run evaluation**, or run the comparison from the repository root:

```powershell
Push-Location backend
..\.venv\Scripts\python.exe -m app.evaluate_cli
Pop-Location
```

The command exits with an explanation if there is no current trained neural artifact. The API equivalent is `POST /api/v1/experiments/evaluate`; `GET /api/v1/experiments` lists saved runs and `GET /api/v1/experiments/{id}` returns one run. The Evaluation page can download `/api/v1/experiments/{id}/plots/roc.svg` and `/api/v1/experiments/{id}/plots/confusion.svg`. These plots are generated from stored numeric results, without raw timing data. Repeating evaluation for the same dataset fingerprint, neural checkpoint, and evaluation source returns its saved run instead of opening the test partition again. A changed dataset requires retraining. Deleting any profile removes saved experiments and the neural checkpoint.

`known-user-test-v1` audits the saved sample IDs, profile ownership, partition overlap, and claimed session separation. It fits a fresh baseline on the **same neural training recordings**, calibrates each model's per-profile threshold on the **same validation recordings**, then scores the **same held-out claim and recording pairs**. The result stores both trial lists, thresholds, FAR and FRR with genuine and impostor denominators, precision, recall, ROC points, confusion counts, split IDs, dataset fingerprint, model versions, training settings, PyTorch version, evaluation source fingerprint, and Git revision when available. Similarity is higher for closer matches; acceptance requires similarity above the profile threshold. The pooled ROC uses each attempt's `similarity − profile threshold` margin, so its zero-margin point matches the reported acceptance decisions.

ROC-AUC and equal error rate are reported only when the test set contains at least 20 genuine and 20 impostor attempts. With fewer attempts, those values are absent and the ROC curve is marked exploratory. The prespecified reference-count study uses 2, 4, 8, and larger available training recordings per profile; it holds the encoder and scaler fixed, recalibrates on validation data, and reports every count on the same test recordings. It measures reference size, not the effect of retraining the neural model. This protocol measures known-user verification only. There is still no real participant dataset in the repository, so no empirical model comparison is claimed until consenting participants provide enough recordings across sessions.
