"""Delivery routes.

The preview and the send run the *same* builder: what the panel shows is the bytes that go on the
wire, not a second implementation of it. Only deliveries that genuinely left the machine are
recorded in the log — previews and downloads are not events.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from app.integrations import ics, payloads, send
from app.models import (
    DeliveryPreview,
    DeliveryRecord,
    DeliveryRequest,
    Report,
    SendResponse,
)
from app.store import Session, store

router = APIRouter(prefix="/api/forms/{sid}", tags=["integrations"])

LIVE = {"teams", "slack", "webhook"}
MAX_LOG = 50

_META = {
    "teams": ("Microsoft Teams", "An Adaptive Card in the channel that owns this form.",
              "Incoming webhook URL", "https://…webhook.office.com/webhookb2/…"),
    "slack": ("Slack", "A message in the channel that owns this form.",
              "Incoming webhook URL", "https://hooks.slack.com/services/…"),
    "webhook": ("Your own system", "The full report as JSON, POSTed to an endpoint you control.",
                "Endpoint URL", "https://your-app.example.com/hooks/minima"),
    "email": ("Email the data owner", "The checklist as a message, with the full report to attach.", None, None),
    "jira": ("Jira", "One ticket per action on the checklist.", None, None),
    "calendar": ("Deletion deadlines", "An .ics file: one reminder per field that has to be deleted.", None, None),
}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


async def _session_report(sid: str) -> tuple[Session, Report]:
    s = await store.get(sid)
    if s is None:
        raise HTTPException(404, f"Unknown form '{sid}'")
    if s.report is None:
        raise HTTPException(409, "Apply the rules first.")
    return s, s.report


def _report_url(request: Request, sid: str) -> str:
    return f"{str(request.base_url).rstrip('/')}/api/forms/{sid}/report?format=html"


def body_for(report: Report, req: DeliveryRequest, *, report_url: str) -> tuple[dict | None, str, str]:
    """(json payload to POST or None, pretty body for the preview, body_format)."""
    d = req.destination
    if d == "teams":
        p = payloads.teams_card(report, report_url=report_url)
        return p, json.dumps(p, indent=2, ensure_ascii=False), "json"
    if d == "slack":
        p = payloads.slack_blocks(report, report_url=report_url)
        return p, json.dumps(p, indent=2, ensure_ascii=False), "json"
    if d == "webhook":
        p = payloads.webhook_payload(report)
        return p, json.dumps(p, indent=2, ensure_ascii=False), "json"
    if d == "email":
        m = payloads.email_message(report, to=req.to, report_url=report_url)
        pretty = (f"To: {m['to'] or '(the person who owns this form)'}\n"
                  f"Subject: {m['subject']}\n"
                  f"Attachment: {m['attachment_name']} ({m['attachment_bytes'] // 1024} KB)\n\n"
                  f"{m['text']}")
        return None, pretty, "text"
    if d == "jira":
        issues = payloads.jira_issues(report, project_key=req.project_key or "DPO")
        return None, json.dumps(issues, indent=2, ensure_ascii=False), "json"
    if d == "calendar":
        return None, ics.render_ics(report, sid=report.form.form_id), "ics"
    raise HTTPException(422, f"Unknown destination '{d}'")


def _summary(report: Report) -> tuple[str, int]:
    dg = payloads.digest(report)
    parts = [f"{dg['n_tasks']} action{'' if dg['n_tasks'] == 1 else 's'}"]
    if dg["n_deadlines"]:
        parts.append(f"{dg['n_deadlines']} deletion deadline{'' if dg['n_deadlines'] == 1 else 's'}")
    if dg["n_flagged"]:
        parts.append(f"{dg['n_flagged']} flagged decision{'' if dg['n_flagged'] == 1 else 's'}")
    return " · ".join(parts), dg["n_tasks"]


# ---------------------------------------------------------------------------
# routes
# ---------------------------------------------------------------------------


@router.post("/deliveries/preview", response_model=DeliveryPreview)
async def preview_delivery(sid: str, req: DeliveryRequest, request: Request) -> DeliveryPreview:
    _, report = await _session_report(sid)
    report_url = _report_url(request, sid)
    _, body, fmt = body_for(report, req, report_url=report_url)
    title, subtitle, url_label, placeholder = _META[req.destination]
    summary, n_tasks = _summary(report)

    note, link = None, None
    if req.destination == "email":
        note = ("Opens your mail app with the checklist. Attach the HTML report from the export card "
                "above — a mail link cannot carry the file itself.")
        link = payloads.mailto_link(report, to=req.to, report_url=report_url)
    elif req.destination == "jira":
        note = "Copy these into Jira — one ticket per action, with the field and the article behind it."
    elif req.destination == "calendar":
        note = f"{ics.n_deadlines(report)} reminders, each 7 days before the field has to be deleted."
        link = f"/api/forms/{sid}/report?format=ics"

    return DeliveryPreview(
        destination=req.destination,
        title=title,
        subtitle=subtitle,
        body_format=fmt,
        body=body,
        summary=summary,
        n_tasks=n_tasks,
        sendable=req.destination in LIVE,
        needs_url=req.destination in LIVE,
        url_label=url_label,
        url_placeholder=placeholder,
        note=note,
        link=link,
    )


@router.post("/deliveries", response_model=SendResponse)
async def send_delivery(sid: str, req: DeliveryRequest, request: Request) -> SendResponse:
    session, report = await _session_report(sid)
    if req.destination not in LIVE:
        raise HTTPException(422, f"{_META[req.destination][0]} hands you the payload — there is nothing to send.")

    payload, _, _ = body_for(report, req, report_url=_report_url(request, sid))
    summary, _ = _summary(report)

    try:
        url = send.validate_url(req.url)
    except ValueError as exc:
        result = send.SendResult(False, None, str(exc))
        target = (req.url or "").strip()[:60] or "(empty)"
    else:
        result = await send.post_json(url, payload or {})
        target = send.redact(url)

    record = DeliveryRecord(
        id=uuid.uuid4().hex[:8],
        destination=req.destination,
        target=target,
        at=datetime.now(timezone.utc),
        ok=result.ok,
        status=result.status,
        detail=result.detail,
        summary=summary,
    )
    session.deliveries = (session.deliveries + [record])[-MAX_LOG:]
    await store.save(session)
    return SendResponse(record=record, log=list(reversed(session.deliveries)))


@router.get("/deliveries", response_model=list[DeliveryRecord])
async def list_deliveries(sid: str) -> list[DeliveryRecord]:
    s = await store.get(sid)
    if s is None:
        raise HTTPException(404, f"Unknown form '{sid}'")
    return list(reversed(s.deliveries))
