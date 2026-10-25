# KeyRhythm

KeyRhythm is a local research application for studying continuous user verification from keystroke timing. The [product requirements](plan.md) and [implementation plan](docs/implementation-plan.md) define the milestone scope.

**Current status: Milestone 2.** Profiles, consented typing capture, timing validation, and local SQLite storage are available. Authentication, training, and model results are planned for later milestones.

## Requirements

- Python 3.11 (tested with 3.11.9 on Windows).
- Node.js 24 (tested with 24.12.0) and npm.
- Git.

## Install

From the repository root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.lock
npm.cmd --prefix frontend ci
```

The lockfiles capture the tested API and frontend dependency set. `backend/requirements.txt` and `backend/requirements-dev.txt` contain broader ranges for future updates. The larger ML packages in `backend/requirements-ml.txt` are for later milestones. In PowerShell on this machine, `npm.cmd` works where the `npm.ps1` shim is blocked by execution policy.

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

The frontend build includes TypeScript checking. Tests cover profile and sample lifecycle, rejection of invalid timing data, text privacy, browser timing capture, consent gating, and dashboard navigation.

## Layout and data policy

```text
frontend/src/                 Dashboard, enrolment, field-scoped capture, API client
frontend/vite.config.ts       React, Tailwind, tests, and local API proxy
frontend/package-lock.json    Tested npm dependency graph
backend/app/main.py           FastAPI health, profile, and sample routes
backend/app/schemas.py        Versioned timing validation and API models
backend/app/database.py       SQLite profile and sample models
backend/tests/                Backend tests
backend/requirements-dev.lock Tested Python API/test dependencies
docs/implementation-plan.md   Milestone gates and research risks
```

The initial version is an academic prototype, not an identity-security product. Timing capture runs only in the designated challenge field after consent. Raw keyboard events and entered challenge text stay transient in the browser; only numeric timing sequences and pseudonymous profile labels are sent. Local databases, generated model artifacts, and environment files are excluded by `.gitignore`.

## Enrolment and timing format

Create a profile, select it, accept the consent notice, and type the displayed sentence exactly. Corrections, paste, composition input, focus loss, repeated keys, and incomplete key releases require a sample restart. The collection target defaults to 10 samples per profile and is configurable through `KEYRHYTHM_ENROLLMENT_TARGET`; this is a UI collection target, not a claim of dataset sufficiency. Deleting a profile deletes its samples. There are no database backups or exports in this milestone; if you make a copy of the SQLite file, manage and delete that copy separately.

The fixed challenge is `the quick brown fox jumps over the lazy dog.` (`fixed-1`, 44 positions). `timing-1` uses monotonic browser event timestamps in **milliseconds**. For each challenge position, `hold_ms[i]` is key-up minus key-down. For positions 1 through 43, `down_down_ms[i]` is the next key-down minus the current key-down; `flight_ms[i]` is the next key-down minus the current key-up, so negative values represent overlapping holds. `long_pauses[i]` is true when `flight_ms[i] >= 750`. `total_ms` is the final key-up minus the first key-down. Arrays are JSON numeric lists stored in SQLite with their challenge and feature versions, a random session ID, and a sample ID. List APIs return metadata and counts, never the timing arrays.

The backend checks versions, array lengths, finite numeric values, plausible bounds, and timing arithmetic. It cannot independently prove which text a browser user typed from a timing-only payload; the browser checks completion, and this local research API assumes an honest client. Browser timer precision and keyboard behavior can vary. The sample target should be revisited before model experiments, with multiple consenting participants and sessions and leakage-safe recording splits.
