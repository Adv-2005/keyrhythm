# KeyRhythm

KeyRhythm is a local research application for studying continuous user verification from keystroke timing. The [product requirements](plan.md) and [implementation plan](docs/implementation-plan.md) define the milestone scope.

**Current status: Milestone 1.** The React dashboard shell and FastAPI health endpoint run locally. Navigation shows the areas planned for later milestones. No typing data is collected and no authentication or model result is available yet.

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

The lockfiles capture the tested Milestone 1 dependency set. `backend/requirements.txt` and `backend/requirements-dev.txt` contain broader ranges for future updates. The larger ML packages in `backend/requirements-ml.txt` are for later milestones and are not needed to run the foundation. In PowerShell on this machine, `npm.cmd` works where the `npm.ps1` shim is blocked by execution policy.

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

Open `http://127.0.0.1:5173`. The status badge requests `/api/v1/health` through Vite's local proxy, which forwards to FastAPI at `http://127.0.0.1:8000`. `frontend/.env.example` documents the default browser API path; copying it to `.env` is optional. The backend database setting in `backend/.env.example` is reserved for Milestone 2 and is not read by the foundation.

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

The frontend build includes TypeScript checking. Tests cover the health endpoint, frontend connectivity states, and dashboard navigation.

## Layout and data policy

```text
frontend/src/                 Dashboard shell and API client
frontend/vite.config.ts       React, Tailwind, tests, and local API proxy
frontend/package-lock.json    Tested npm dependency graph
backend/app/main.py           FastAPI app and versioned health route
backend/tests/                Backend tests
backend/requirements-dev.lock Tested Python API/test dependencies
docs/implementation-plan.md   Milestone gates and research risks
```

The initial version is an academic prototype, not an identity-security product. Future timing capture must stay within the designated challenge field, require participant consent, and avoid sending or storing typed text or raw keyboard events. Local databases, generated model artifacts, and environment files are excluded by `.gitignore`.
