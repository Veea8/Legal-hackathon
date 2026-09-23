# Data Minimiser

Privacy-by-design assistant for forms, onboarding flows and CRM schemas (Legal Hackathon 2026, Track 1).
It reviews every field of a form and proposes **keep / make optional / remove / better explain**, with a
plain-language reason and the GDPR / revFADP article behind it.

How it works, in one line: **deterministic compliance checks** and an **AI assessment** (Apertus) look at the
field definitions independently, a **merge** takes the stricter view, a **human reviews** and decides, and a
**deterministic engine** applies the final rules and writes the report. The AI never sees data values,
only field names, labels, types and purposes.

- Architecture, contracts, check table, API: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- Model access (Swisscom Apertus endpoint, fallback): [`docs/APERTUS.md`](docs/APERTUS.md)

## Run locally

Backend (Python 3.12+):

```bash
cd backend
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
cp .env.example .env            # add APERTUS_API_KEY; without it the app runs with checks only
./.venv/bin/uvicorn app.main:app --reload --port 8000
```

Frontend (Node 20+):

```bash
cd frontend
npm install
npm run dev                     # http://localhost:5173, proxies /api to :8000
```

## Tests, benchmark, eval

```bash
cd backend
./.venv/bin/python -m pytest -q
./.venv/bin/python scripts/benchmark_apertus.py     # latency + JSON validity of the model
./.venv/bin/python scripts/eval.py --checks-only    # accuracy vs the jury labels (offline)
./.venv/bin/python scripts/precompute_demo.py       # cache AI results for the 5 demo forms
./.venv/bin/python scripts/eval.py --cached
```

## Docker

```bash
docker build -t data-minimiser .
docker run -p 8000:8000 --env-file backend/.env data-minimiser   # open http://localhost:8000
```

## Status (23 Sep 2026)

Built and verified: loader, knowledge base, compliance checks, AI module (offline-tested), merge,
engine, report, API, React frontend (production build served by the backend), 26 backend tests,
checks-only eval (flag 29/29, lenient 27/29 against the jury labels).
Not yet verified: the Dockerfile (the Docker daemon was not running when it was written) and any
live Apertus call (no key in `backend/.env` yet).

Still to do on the day, in order:
1. Put the Swisscom key in `backend/.env`, run `scripts/benchmark_apertus.py`.
2. Run `scripts/precompute_demo.py`, then `scripts/eval.py --cached`; iterate on `app/ai/prompts.py` if needed.
3. Commit `backend/app/cache/*.json` so graders get instant results.
4. Deploy the Docker image somewhere public; check that ports 8000 / 5173 are free locally before a live demo.
5. Stretch: paste-to-schema UI polish, data-flow diagram, record minimisation module (`engine/records.py`).

## Repository layout

```
backend/app/     FastAPI app: models (contracts), loaders, kb, checks, ai, merge, engine, report
backend/scripts/ benchmark, precompute cache, eval
backend/tests/   pytest
frontend/        Vite + React + TypeScript
data/            challenge workbook and notes (unchanged)
docs/            architecture and model access
```
