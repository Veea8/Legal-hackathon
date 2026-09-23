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

Built and verified: loader, knowledge base, compliance checks, AI module, merge, engine, report, API,
React frontend (production build served by the backend), 26 backend tests. The Apertus key is in
`backend/.env` (gitignored) and live: all five demo forms are precomputed into `app/cache/`.

**Eval standing (29 jury-labelled fields, targets lenient ≥ 25, flag ≥ 27):**

| run | flag acc | lenient |
|---|---|---|
| checks only | **29/29** | **27/29** |
| checks + AI, before the decision ladder | 22/29 | 18/29 |
| checks + AI, now | **28/29** | **25/29** |

The deterministic checks alone clear both targets. The AI was *lowering* the score: it escalated any
field whose stated purpose was merely brief, and the merge rule takes the stricter of the two. Stating
principles in `SYSTEM_PROMPT` did not change that; an ordered **decision ladder** ("stop at the first
matching line") did. The four remaining misses are judgement calls where we come out stricter than the
jury — deliberately left alone rather than over-fitted to 29 labels; the decision drawer is where a
human softens them.

After any prompt change: `scripts/eval.py --live`, then `scripts/precompute_demo.py`, or the demo serves
the old assessments from `app/cache/`.

Not yet verified: the Dockerfile (the Docker daemon was not running when it was written).

Still to do, in order:
1. Close the AI eval gap against the checks-only baseline (`app/ai/prompts.py`, then `scripts/eval.py --live`).
2. Commit `backend/app/cache/*.json` so graders get instant results.
3. Deploy the Docker image somewhere public; check that ports 8000 / 5173 are free locally before a live demo.
4. Stretch: record minimisation module (`engine/records.py`), paste-to-schema UI (the API endpoint exists, the screen does not).

## Repository layout

```
backend/app/     FastAPI app: models (contracts), loaders, kb, checks, ai, merge, engine, report
backend/scripts/ benchmark, precompute cache, eval
backend/tests/   pytest
frontend/        Vite + React + TypeScript
data/            challenge workbook and notes (unchanged)
docs/            architecture and model access
```
