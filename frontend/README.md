# Frontend (React + Vite + TypeScript)

```
cd frontend
npm install
npm run dev                          # http://localhost:5173, proxies /api to http://localhost:8000
API_PROXY=http://localhost:8001 npm run dev   # if the backend runs elsewhere
npm run build                        # type-check + build to dist/ (served by the backend at /)
```

Backend: `cd backend && ./.venv/bin/uvicorn app.main:app --port 8000`

Pages: `/` Start · `/forms/:id/context` Context (no AI) · `/forms/:id/review` Review · `/forms/:id/result` Result · `/about`.
Contracts: `src/types.ts` mirrors `backend/app/models.py` — change both together. API client: `src/api.ts`.
