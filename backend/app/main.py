"""Data Minimiser API. See docs/ARCHITECTURE.md section 8.

Session ids double as `form_id` in every payload the frontend sees; the original demo id (F001…) is
kept on the session so cached results can be served.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from app.checks.rules import run_checks
from app.engine.apply import apply as apply_engine
from app.kb import load_kb
from app.loaders.xlsx import load_demo_forms, load_upload
from app.merge import OverrideError, apply_overrides, build_ruleset
from app.models import (
    AIAssessment,
    ApplyResponse,
    CheckResult,
    CreateFormRequest,
    DemoFormInfo,
    FormSchema,
    HealthResponse,
    KBEntry,
    OverridesRequest,
    RuleSet,
)
from app.report.build import build_report, render_csv, render_html
from app.store import Session, store

BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env")

CACHE_DIR = Path(__file__).with_name("cache")
FRONTEND_DIST = BACKEND_DIR.parent / "frontend" / "dist"
DEMO_FORMS: dict[str, FormSchema] = {f.form_id: f for f in load_demo_forms()}

app = FastAPI(title="Data Minimiser API", version="0.1")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_tasks: dict[str, asyncio.Task] = {}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _session(sid: str) -> Session:
    s = store.get(sid)
    if s is None:
        raise HTTPException(404, f"Unknown form '{sid}'")
    return s


def _cache_path(demo_form_id: Optional[str]) -> Optional[Path]:
    if not demo_form_id:
        return None
    p = CACHE_DIR / f"{demo_form_id}.json"
    return p if p.exists() else None


def _schema_unchanged(session: Session) -> bool:
    demo = DEMO_FORMS.get(session.demo_form_id or "")
    if demo is None:
        return False
    a = [f.model_dump() for f in session.schema.fields]
    b = [f.model_dump() for f in demo.fields]
    return a == b and session.schema.stage == demo.stage


def _ai():
    """Lazy import so the API runs before / without the AI module."""
    try:
        from app.ai import assess as ai_assess  # noqa: WPS433
    except Exception:  # noqa: BLE001 - module missing or half-written: run checks-only
        return None
    return ai_assess


def _partial_ruleset(session: Session, done: dict[str, Optional[AIAssessment]], errors: dict[str, str], model: Optional[str]) -> RuleSet:
    sub = session.schema.model_copy(deep=True)
    sub.fields = [f for f in sub.fields if f.field_id in done]
    checks = [c for c in session.checks if c.field_id in done]
    rs = build_ruleset(sub, checks, done, ai_model=model, ai_errors=errors, status="running")
    rs.fields_total = len(session.schema.fields)
    rs.fields_done = len(done)
    return rs


async def _run_analysis(session: Session) -> None:
    session.checks = run_checks(session.schema)
    ai = _ai()
    model = ai.ai_model_name() if ai else None
    done: dict[str, Optional[AIAssessment]] = {}
    errors: dict[str, str] = {}
    session.ruleset = _partial_ruleset(session, done, errors, model)

    if ai is None or not ai.ai_available():
        errors = {f.field_id: "AI not configured (no APERTUS_API_KEY)" for f in session.schema.fields}
        assessments: dict[str, Optional[AIAssessment]] = {f.field_id: None for f in session.schema.fields}
    else:
        def on_field(field_id: str, assessment: Optional[AIAssessment], error: Optional[str]) -> None:
            done[field_id] = assessment
            if error:
                errors[field_id] = error
            session.ruleset = _partial_ruleset(session, done, errors, model)

        assessments, errs = await ai.assess_form(session.schema, on_field=on_field)
        errors.update(errs)

    session.ruleset = build_ruleset(
        session.schema, session.checks, assessments, ai_model=model, ai_errors=errors, status="proposed"
    )


# ---------------------------------------------------------------------------
# routes
# ---------------------------------------------------------------------------


@app.get("/api/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    ai = _ai()
    return HealthResponse(
        ok=True,
        model=ai.ai_model_name() if ai else None,
        base_url_set=bool(os.getenv("APERTUS_BASE_URL")),
        api_key_set=bool(os.getenv("APERTUS_API_KEY")),
        cached_forms=sorted(p.stem for p in CACHE_DIR.glob("F*.json")),
        json_mode=ai.json_mode_supported() if ai else None,
    )


@app.get("/api/kb", response_model=list[KBEntry])
async def kb() -> list[KBEntry]:
    return load_kb()


@app.get("/api/demo-forms", response_model=list[DemoFormInfo])
async def demo_forms() -> list[DemoFormInfo]:
    return [
        DemoFormInfo(
            form_id=f.form_id, name=f.name, business_context=f.business_context,
            n_fields=len(f.fields), cached=_cache_path(f.form_id) is not None,
        )
        for f in DEMO_FORMS.values()
    ]


@app.post("/api/forms", response_model=FormSchema)
async def create_form(req: CreateFormRequest) -> FormSchema:
    if req.source == "demo":
        demo = DEMO_FORMS.get(req.form_id or "")
        if demo is None:
            raise HTTPException(404, f"Unknown demo form '{req.form_id}'")
        s = store.create(demo, demo_form_id=demo.form_id)
    else:
        if not req.text or not req.text.strip():
            raise HTTPException(422, "Paste some text describing the form fields.")
        try:
            from app.ai import extract  # noqa: WPS433
        except ImportError:
            raise HTTPException(501, "AI text extraction is not available yet.")
        schema = await extract.extract_fields(req.text, name=req.name, business_context=req.business_context)
        s = store.create(schema)
    s.schema.form_id = s.id
    return s.schema


@app.post("/api/forms/upload", response_model=list[FormSchema])
async def upload_form(file: UploadFile = File(...)) -> list[FormSchema]:
    content = await file.read()
    try:
        forms = load_upload(file.filename or "upload.csv", content)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(422, f"Could not parse the file: {exc}")
    if not forms or not any(f.fields for f in forms):
        raise HTTPException(422, "No fields found. Use the challenge column format (form_id, field_name, ...).")
    out: list[FormSchema] = []
    for f in forms:
        s = store.create(f)
        s.schema.form_id = s.id
        out.append(s.schema)
    return out


@app.get("/api/forms/{sid}", response_model=FormSchema)
async def get_form(sid: str) -> FormSchema:
    return _session(sid).schema


@app.put("/api/forms/{sid}", response_model=FormSchema)
async def update_form(sid: str, schema: FormSchema) -> FormSchema:
    s = _session(sid)
    schema.form_id = s.id
    s.schema = schema
    s.checks, s.ruleset, s.minimised, s.report = [], None, None, None
    return s.schema


@app.get("/api/forms/{sid}/checks", response_model=list[CheckResult])
async def get_checks(sid: str) -> list[CheckResult]:
    s = _session(sid)
    s.checks = run_checks(s.schema)
    return s.checks


@app.post("/api/forms/{sid}/analyze", response_model=RuleSet)
async def analyze(sid: str, live: bool = Query(False)) -> RuleSet:
    s = _session(sid)
    cache = _cache_path(s.demo_form_id)
    if not live and cache and _schema_unchanged(s):
        rs = RuleSet.model_validate_json(cache.read_text(encoding="utf-8"))
        rs.form_id = s.id
        rs.cached = True
        rs.status = "proposed"
        s.checks = run_checks(s.schema)
        s.ruleset = rs
        return rs
    task = _tasks.get(sid)
    if task and not task.done():
        return s.ruleset or RuleSet(form_id=s.id, fields_total=len(s.schema.fields))
    s.checks = run_checks(s.schema)
    s.ruleset = RuleSet(form_id=s.id, status="running", fields_total=len(s.schema.fields))
    _tasks[sid] = asyncio.create_task(_run_analysis(s))
    return s.ruleset


@app.get("/api/forms/{sid}/analysis", response_model=RuleSet)
async def get_analysis(sid: str) -> RuleSet:
    s = _session(sid)
    if s.ruleset is None:
        raise HTTPException(404, "Analysis not started. POST /analyze first.")
    task = _tasks.get(sid)
    if task and task.done() and task.exception() is not None and s.ruleset.status == "running":
        raise HTTPException(500, f"Analysis failed: {task.exception()}")
    return s.ruleset


@app.put("/api/forms/{sid}/rules", response_model=RuleSet)
async def put_rules(sid: str, req: OverridesRequest) -> RuleSet:
    s = _session(sid)
    if s.ruleset is None or s.ruleset.status == "running":
        raise HTTPException(409, "Analysis not finished yet.")
    try:
        s.ruleset = apply_overrides(s.ruleset, req.overrides)
    except OverrideError as exc:
        raise HTTPException(422, str(exc))
    return s.ruleset


@app.post("/api/forms/{sid}/apply", response_model=ApplyResponse)
async def apply_rules(sid: str) -> ApplyResponse:
    s = _session(sid)
    if s.ruleset is None or s.ruleset.status == "running":
        raise HTTPException(409, "Analysis not finished yet.")
    s.minimised = apply_engine(s.schema, s.ruleset)
    s.report = build_report(s.schema, s.ruleset, s.minimised)
    s.ruleset.status = "applied"
    return ApplyResponse(minimised=s.minimised, report=s.report)


@app.get("/api/forms/{sid}/report")
async def get_report(sid: str, format: str = Query("json", pattern="^(json|csv|html)$")):
    s = _session(sid)
    if s.report is None:
        raise HTTPException(409, "Apply the rules first.")
    if format == "csv":
        return PlainTextResponse(
            render_csv(s.report), media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="minimisation-report-{sid}.csv"'},
        )
    if format == "html":
        return HTMLResponse(render_html(s.report))
    return JSONResponse(json.loads(s.report.model_dump_json()))


# ---------------------------------------------------------------------------
# frontend (production build served from the same origin)
# ---------------------------------------------------------------------------

if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str):
        candidate = FRONTEND_DIST / path
        if path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
