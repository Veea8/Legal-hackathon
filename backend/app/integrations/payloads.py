"""The same report, shaped for the places the work actually happens.

Pure functions: `Report` in, payload out. No I/O, no network, no clock beyond the report's own
`generated_at`. Every builder is driven by `representative_tasks()` from `report/build.py`, so the
Teams card, the Slack message, the email, the Jira tickets and the HTML report can never drift
apart — the checklist is derived once and shaped many times.
"""

from __future__ import annotations

from typing import Any, Optional

from app.models import Report
from app.report.build import TASK_BADGE, pretty_date, render_html, representative_tasks

# Teams and Slack are notifications, not reports: past a handful of lines nobody reads them, and
# Slack caps a section at 3000 characters anyway. The full list is one click away.
MAX_TASKS = 8

_COUNT_LABEL = {"keep": "keep", "better_explain": "explain", "make_optional": "optional", "remove": "remove"}
_GROUP_LABEL = {"change": "Change the form", "retention": "Set up deletion", "signoff": "Sign off in writing"}
_PRIORITY = {"change": "High", "retention": "Medium", "signoff": "High"}


def _clip(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def digest(report: Report) -> dict[str, Any]:
    """Everything the shaped payloads need, derived once."""
    tasks = representative_tasks(report)
    s = report.summary
    return {
        "tasks": tasks,
        "shown": tasks[:MAX_TASKS],
        "overflow": max(0, len(tasks) - MAX_TASKS),
        "n_tasks": len(tasks),
        "n_deadlines": sum(1 for r in report.rows if r.delete_by),
        "n_flagged": s.n_overrides_flagged,
        "counts": {k: v for k, v in s.counts.items() if v},
    }


def headline(report: Report) -> tuple[str, str]:
    d = digest(report)
    n = d["n_tasks"]
    title = (
        f"{report.form.name} — nothing to change"
        if n == 0
        else f"{report.form.name} — {n} action{'' if n == 1 else 's'} for the form owner"
    )
    counts = " · ".join(f"{v} {_COUNT_LABEL.get(k, k)}" for k, v in d["counts"].items())
    return title, f"{report.summary.n_fields} fields reviewed · {counts}"


def _task_line(t: dict[str, str]) -> str:
    return f"{TASK_BADGE.get(t['action'], t['action'])} — {t['label']}: {t['task']}"


# ---------------------------------------------------------------------------
# Microsoft Teams
# ---------------------------------------------------------------------------


def teams_card(report: Report, *, report_url: Optional[str] = None) -> dict[str, Any]:
    """Adaptive Card in the envelope an incoming webhook expects (not the retired MessageCard)."""
    d = digest(report)
    title, sub = headline(report)

    body: list[dict[str, Any]] = [
        {"type": "TextBlock", "text": title, "size": "Large", "weight": "Bolder", "wrap": True},
        {"type": "TextBlock", "text": sub, "isSubtle": True, "spacing": "None", "wrap": True},
        {"type": "FactSet", "facts": [
            {"title": "Fields reviewed", "value": str(report.summary.n_fields)},
            {"title": "Actions", "value": str(d["n_tasks"])},
            {"title": "Deletion deadlines", "value": str(d["n_deadlines"])},
            {"title": "Flagged decisions", "value": str(d["n_flagged"])},
            {"title": "Special-category fields", "value": str(report.summary.n_special_category)},
        ]},
    ]

    if d["shown"]:
        body.append({"type": "TextBlock", "text": "Actions for the data protection representative",
                     "weight": "Bolder", "wrap": True, "separator": True})
        last_kind = None
        for t in d["shown"]:
            if t["kind"] != last_kind:
                body.append({"type": "TextBlock", "text": _GROUP_LABEL[t["kind"]], "isSubtle": True,
                             "size": "Small", "spacing": "Medium", "wrap": True})
                last_kind = t["kind"]
            body.append({"type": "TextBlock", "text": _clip(f"**{t['label']}** — {t['task']}", 500),
                         "wrap": True, "spacing": "Small"})
    if d["overflow"]:
        body.append({"type": "TextBlock", "text": f"+{d['overflow']} more in the full report",
                     "isSubtle": True, "wrap": True})

    body.append({"type": "TextBlock", "wrap": True, "isSubtle": True, "size": "Small", "separator": True,
                 "text": "Decided by a human. The model never saw a single data value — only field names, "
                         "labels and stated purposes."})

    card: dict[str, Any] = {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": body,
    }
    if report_url:
        card["actions"] = [{"type": "Action.OpenUrl", "title": "Open the full report", "url": report_url}]

    return {"type": "message", "attachments": [{
        "contentType": "application/vnd.microsoft.card.adaptive",
        "contentUrl": None,
        "content": card,
    }]}


# ---------------------------------------------------------------------------
# Slack
# ---------------------------------------------------------------------------


def slack_blocks(report: Report, *, report_url: Optional[str] = None) -> dict[str, Any]:
    d = digest(report)
    title, sub = headline(report)

    blocks: list[dict[str, Any]] = [
        {"type": "header", "text": {"type": "plain_text", "text": _clip(title, 150)}},
        {"type": "section", "fields": [
            {"type": "mrkdwn", "text": f"*Fields reviewed*\n{report.summary.n_fields}"},
            {"type": "mrkdwn", "text": f"*Actions*\n{d['n_tasks']}"},
            {"type": "mrkdwn", "text": f"*Deletion deadlines*\n{d['n_deadlines']}"},
            {"type": "mrkdwn", "text": f"*Flagged decisions*\n{d['n_flagged']}"},
        ]},
    ]

    for kind in ("change", "retention", "signoff"):
        items = [t for t in d["shown"] if t["kind"] == kind]
        if not items:
            continue
        lines = "\n".join(f"• *{t['label']}* — {t['task']}" for t in items)
        blocks.append({"type": "divider"})
        blocks.append({"type": "section", "text": {
            "type": "mrkdwn", "text": _clip(f"*{_GROUP_LABEL[kind]}*\n{lines}", 3000)}})

    if d["overflow"]:
        blocks.append({"type": "context", "elements": [
            {"type": "mrkdwn", "text": f"_+{d['overflow']} more in the full report_"}]})

    if report_url:
        blocks.append({"type": "actions", "elements": [{
            "type": "button", "text": {"type": "plain_text", "text": "Open the full report"},
            "url": report_url}]})

    blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": _clip(
        f"{sub} · decided by a human · the model never saw a data value"
        f"{' · ' + report.ai_model if report.ai_model else ''}", 3000)}]})

    # Slack caps a message at 50 blocks; MAX_TASKS keeps us far below, this is the guard rail.
    return {"text": _clip(title, 3000), "blocks": blocks[:50]}


# ---------------------------------------------------------------------------
# Generic webhook
# ---------------------------------------------------------------------------


def webhook_payload(report: Report) -> dict[str, Any]:
    """The whole thing, machine-readable — top-level keys so it reads well in a webhook inspector."""
    d = digest(report)
    title, _ = headline(report)
    return {
        "source": "minima",
        "event": "form.minimised",
        "title": title,
        "form": report.form.model_dump(),
        "summary": report.summary.model_dump(),
        "actions": d["tasks"],
        "deadlines": [
            {"field_id": r.field_id, "label": r.label, "retention_days": r.retention_days, "delete_by": r.delete_by}
            for r in report.rows if r.delete_by
        ],
        "no_longer_collected": report.no_longer_collected,
        "report": report.model_dump(mode="json"),
    }


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------


def email_message(report: Report, *, to: str = "", report_url: Optional[str] = None) -> dict[str, Any]:
    d = digest(report)
    title, sub = headline(report)
    html = render_html(report)

    lines = [title, sub, ""]
    for kind in ("change", "retention", "signoff"):
        items = [t for t in d["tasks"] if t["kind"] == kind]
        if not items:
            continue
        lines.append(f"{_GROUP_LABEL[kind].upper()}")
        lines += [f"  - {t['label']}: {t['task']}" for t in items]
        lines.append("")
    if report_url:
        lines.append(f"Full report: {report_url}")
    lines.append("")
    lines.append("Every decision in this list was made by a person. The model only ever saw field names, "
                 "labels and stated purposes — never a data value.")

    return {
        "to": to,
        "subject": _clip(f"Data minimisation: {title}", 160),
        "text": "\n".join(lines),
        "html": html,
        "attachment_name": f"minimisation-report-{report.form.form_id}.html",
        "attachment_bytes": len(html.encode("utf-8")),
    }


def mailto_link(report: Report, *, to: str = "", report_url: Optional[str] = None) -> str:
    """A short mailto — the full body blows past the ~2000 char limit Outlook and Gmail choke on."""
    from urllib.parse import quote

    d = digest(report)
    title, sub = headline(report)
    body = [title, sub, ""]
    body += [f"- {t['label']}: {_clip(t['task'], 110)}" for t in d["tasks"][:5]]
    if len(d["tasks"]) > 5:
        body.append(f"(+{len(d['tasks']) - 5} more in the full report)")
    if report_url:
        body += ["", f"Full report: {report_url}"]
    return f"mailto:{quote(to)}?subject={quote(_clip(title, 160))}&body={quote(chr(10).join(body))}"


# ---------------------------------------------------------------------------
# Jira
# ---------------------------------------------------------------------------


def jira_issues(report: Report, *, project_key: str = "DPO") -> list[dict[str, Any]]:
    """One issue per checklist item. Keys are deterministic, so the same report always reads the same."""
    by_field = {r.field_id: r for r in report.rows}
    issues: list[dict[str, Any]] = []
    for i, t in enumerate(representative_tasks(report)):
        row = by_field.get(t["field_id"])
        desc = [t["task"], "", f"Field: {t['field_id']} ({t['label']})"]
        if row is not None:
            desc.append(f"Decision: {row.owner_decision}")
            if row.kb_titles:
                desc.append(f"Legal basis: {'; '.join(row.kb_titles)}")
            if row.reason:
                desc.append(f"Why: {row.reason}")
        issues.append({
            "key": f"{project_key}-{100 + i}",
            "issuetype": "Task",
            "summary": _clip(f"{TASK_BADGE.get(t['action'], t['action'])}: {t['label']} ({report.form.name})", 120),
            "description": "\n".join(desc),
            "labels": ["data-minimisation", report.form.form_id, t["kind"]],
            "priority": _PRIORITY[t["kind"]],
            "duedate": row.delete_by if (row is not None and t["kind"] == "retention") else None,
        })
    return issues
