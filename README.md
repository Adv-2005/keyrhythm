# KeyRhythm

KeyRhythm is a local research application for studying continuous user verification from keystroke timing. The [product requirements](plan.md) and [implementation plan](docs/implementation-plan.md) define the milestone scope.

**Current status: Milestone 4.** Profiles, consented typing capture, local SQLite storage, baseline verification, and Siamese training and inference are available. Final held-out model comparison is planned for Milestone 5.

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

The lockfiles capture the tested API and frontend dependency set. `backend/requirements.txt` and `backend/requirements-dev.txt` contain broader ranges for future updates. The baseline uses the API dependencies and Python's standard library. `backend/requirements-ml.txt` adds PyTorch for Milestone 4 and declares the analysis packages for Milestone 5. Neural runs record the installed PyTorch version with their configuration. In PowerShell on this machine, `npm.cmd` works where the `npm.ps1` shim is blocked by execution policy.

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

The frontend build includes TypeScript checking. Tests cover profile and sample lifecycle, invalid timing data, text privacy, browser capture and consent, recording splits, pair labels, shared encoder shapes, repeatable neural training, checkpoint loading, model staleness, and live result display. Neural tests are skipped if PyTorch is not installed.

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
backend/tests/                Backend tests
backend/requirements-dev.lock Tested Python API/test dependencies
docs/implementation-plan.md   Milestone gates and research risks
```

The initial version is an academic prototype, not an identity-security product. Timing capture runs only in the designated challenge field after consent. Raw keyboard events and entered challenge text stay transient in the browser; only numeric timing sequences and pseudonymous profile labels are sent. Local databases, generated model artifacts, and environment files are excluded by `.gitignore`.

## Enrolment and timing format

Create a profile, select it, accept the consent notice, and type the displayed sentence exactly. Corrections, paste, composition input, focus loss, repeated keys, and incomplete key releases require a sample restart. The collection target defaults to 10 samples per profile and is configurable through `KEYRHYTHM_ENROLLMENT_TARGET`; this is a UI collection target, not a claim of dataset sufficiency. Deleting a profile deletes its samples. There are no database backups or exports in this milestone; if you make a copy of the SQLite file, manage and delete that copy separately.

The fixed challenge is `the quick brown fox jumps over the lazy dog.` (`fixed-1`, 44 positions). `timing-1` uses monotonic browser event timestamps in **milliseconds**. For each challenge position, `hold_ms[i]` is key-up minus key-down. For positions 1 through 43, `down_down_ms[i]` is the next key-down minus the current key-down; `flight_ms[i]` is the next key-down minus the current key-up, so negative values represent overlapping holds. `long_pauses[i]` is true when `flight_ms[i] >= 750`. `total_ms` is the final key-up minus the first key-down. Arrays are JSON numeric lists stored in SQLite with their challenge and feature versions, a random session ID, and a sample ID. List APIs return metadata and counts, never the timing arrays.

The backend checks versions, array lengths, finite numeric values, plausible bounds, and timing arithmetic. It cannot independently prove which text a browser user typed from a timing-only payload; the browser checks completion, and this local research API assumes an honest client. Browser timer precision and keyboard behavior can vary. The sample target should be revisited before model experiments, with multiple consenting participants and sessions and leakage-safe recording splits.

## Baseline verification

Collect at least **six valid samples for each of two profiles**, then open **Authentication** and choose **Train baseline**. The six-sample minimum is a software gate for fitting and calibration; the 10-sample enrolment target remains the default collection goal. More participants and sessions are needed for a credible study. Training fits all eligible profiles together and stores one baseline artifact per profile in the same local SQLite database. Adding or deleting a sample makes the artifacts stale; train again before verification. Deleting a profile also deletes its artifact. A fresh verification sample is processed for inference and is not saved.

`baseline-features-v1` is a 44 × 3 matrix. Each challenge position has key hold duration, key-down-to-key-down interval, and a long-pause flag. The final position has zero interval and pause padding. The scaler uses the median and median absolute deviation of **training recordings only**, with scale floors of 20 ms for holds and 30 ms for intervals. Each profile prototype is the position-wise median of its normalized training recordings. Verification uses the root-mean-square distance to that prototype. The displayed similarity is `1 / (1 + distance)` and is **not a probability**; larger values indicate a closer match.

For each eligible profile, validation reserves at least two original recordings. It separates entire collection sessions when enough training and validation recordings remain, and otherwise splits by recording ID. The threshold minimizes the average of false acceptance and false rejection on genuine and other-profile **validation** recordings; ties favor fewer false acceptances. A sample is accepted only when its similarity is strictly greater than the threshold. The API returns validation calibration rates and counts as preliminary diagnostics. These rates are not a held-out performance estimate. Milestone 5 will define and run the final test protocol. Keep future test recordings separate before fitting any scaler, prototype, or threshold.

The baseline API endpoints are `POST /api/v1/models/train`, `GET /api/v1/models/status`, and `POST /api/v1/authenticate`. The UI calls them directly. Training returns a conflict response until the minimum data requirement is met. Authentication returns a similarity score, threshold, decision, model version, and calibration context; it returns a conflict response when enrollment has changed since training.

## Siamese training and verification

Collect at least **10 valid recordings from each of three consenting profiles** before neural training. This is a functional software minimum, not evidence of reliable biometric accuracy. There is no collected participant dataset in this repository. The Model laboratory shows eligibility, accepts an epoch count and embedding size, and starts a synchronous local CPU run. The request remains busy until training and checkpoint saving finish. A failed run returns an error and does not replace the previous checkpoint.

The `siamese-cnn-v1` encoder uses two shared one-dimensional convolution layers, temporal pooling, and a configurable embedding projection (32 dimensions by default). Training uses balanced positive and negative recording pairs with contrastive loss. Both models use the same 44 × 3 `baseline-features-v1` timing matrix. A robust scaler is fitted on neural training recordings only; normalized inputs are clipped to [-10, 10] in both training and inference. Embeddings have unit length. The stored profile reference is the normalized mean of its training embeddings. Euclidean embedding distance is converted to similarity as `1 / (1 + distance)`. This score is not a probability.

Each eligible profile reserves original recordings for training, validation, and a held-out test partition **before** any scaling or pair construction. When at least three collection sessions have enough recordings, entire sessions are separated; otherwise, the split is by recording ID and the UI reports possible session overlap. Positive and negative pairs are formed within training or validation only. The best checkpoint is chosen by validation pair loss. Profile thresholds minimize balanced validation error using validation genuine and impostor samples. Held-out recordings are neither embedded nor scored during Milestone 4 training; Milestone 5 will use them for the final comparison. The artifact stores sample ID splits, seed, architecture and training settings, loss history, PyTorch version, feature version, and dataset fingerprint. Adding a sample makes the model stale. Deleting any profile removes the global neural checkpoint because its weights may contain information derived from that profile.

The neural endpoints are `POST /api/v1/models/siamese/train` and `GET /api/v1/models/siamese/status`. The training request accepts `epochs`, `batch_size`, `learning_rate`, `embedding_dim`, `margin`, and `seed`; omitted values use documented defaults in the API schema. To verify with the neural model, use Authentication → Siamese CNN or set `model_type: "siamese"` in `POST /api/v1/authenticate`. The response includes the actual embedding similarity, validation threshold, decision, and calibration counts. The status endpoint identifies missing data, an untrained model, a stale artifact, or a ready checkpoint. The laboratory's FAR and FRR are **validation calibration diagnostics**, not held-out performance estimates. More participants and sessions are needed before making research claims about generalization.
