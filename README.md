# KeyRhythm

KeyRhythm is a planned local research application for continuous user verification from keystroke timing. The product requirements are in [plan.md](plan.md). This repository is currently at **Milestone 0**: it contains planning and dependency declarations, but no runnable application or tests yet.

## Requirements and setup

- Python 3.11 (the version available in the inspected workspace).
- Node.js 24 (available in the inspected workspace; use a Node version supported by the chosen Vite release).
- npm and Git.

From the repository root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-ml.txt
Copy-Item backend\.env.example backend\.env
Copy-Item frontend\.env.example frontend\.env
npm.cmd --prefix frontend install
```

The two `pip install` commands separate the API/test tools from the larger machine-learning stack. For a lighter environment during Milestone 1, omit the `requirements-ml.txt` command. `npm.cmd` avoids a PowerShell execution-policy error seen with `npm` on this machine. These commands prepare dependencies; `npm run dev`, an API server, and tests will become available in Milestone 1. Do not use the application for actual participant data collection until consent, validation, and deletion flows are implemented in Milestone 2.

Dependency ranges are declared now. The first successful frontend install should commit `frontend/package-lock.json`; the Python environment should be locked to tested versions during Milestone 1. Until then, these installs are repeatable commands but are not bit-for-bit reproducible over time.

Milestone 0 checks (from the repository root):

```powershell
python --version
node --version
npm.cmd --version
python -c "import json; json.load(open('frontend/package.json', encoding='utf-8')); print('package.json valid')"
git status --short
git check-ignore -v --no-index backend/.env frontend/.env backend/data/keyrhythm.sqlite3
```

Package installation needs access to the relevant registries. The Milestone 0 npm lockfile resolution attempt could not complete in the inspected environment; no lockfile or installed dependencies are claimed here.

## Layout

```text
plan.md                  Product requirements (source of truth)
docs/implementation-plan.md  Milestones, dependencies, decisions, risks
frontend/package.json    Planned React/Vite dependencies
frontend/src/            Future UI and scoped typing capture
frontend/.env.example    Future browser API base URL
backend/requirements*.txt Planned API, ML, and test dependencies
backend/app/             Future FastAPI routes, persistence, and ML modules
backend/tests/           Future backend tests
backend/.env.example     Future local database URL
```

The directories under `src/`, `app/`, and `tests/` are empty placeholders. Configuration examples are not yet consumed by code. Milestone 1 will provide startup commands and working tests.

## Local data policy

The planned browser collector will observe timing only in the designated challenge field. It must discard key values and raw keyboard events before sending a sample. Timing sequences are behavioural biometric data: collect with consent, keep them local by default, and make profile deletion remove associated records. The `.gitignore` excludes local databases, generated artifacts, and environment files. It cannot prevent an intentional `git add -f` or protect data already committed.

See [the implementation plan](docs/implementation-plan.md) for the milestone gates and unresolved protocol decisions.
