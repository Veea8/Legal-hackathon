"""Deletion deadlines as a calendar file.

"Has to be deleted by <date>" is the one decision in the report that expires. A report gets filed;
a calendar entry with a reminder gets acted on. Hand-written rather than pulled from a library —
it is sixty lines and the project takes no new dependencies.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from app.models import Report
from app.report.build import representative_tasks

REMINDER_DAYS = 7


def _esc(s: str) -> str:
    """RFC 5545 text escaping. Order matters: backslash first, or it escapes its own escapes."""
    return (
        str(s).replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def _fold(line: str) -> list[str]:
    """Content lines are capped at 75 octets; continuations start with a single space."""
    raw = line.encode("utf-8")
    if len(raw) <= 75:
        return [line]
    out, cur = [], raw
    limit = 75
    while len(cur) > limit:
        cut = limit
        while cut > 0 and (cur[cut] & 0xC0) == 0x80:  # never split a UTF-8 sequence
            cut -= 1
        out.append(cur[:cut].decode("utf-8"))
        cur = cur[cut:]
        limit = 74  # the leading space counts toward the 75
    out.append(cur.decode("utf-8"))
    return [out[0]] + [" " + p for p in out[1:]]


def render_ics(report: Report, *, sid: str = "", reminder_days: int = REMINDER_DAYS) -> str:
    stamp = report.generated_at.strftime("%Y%m%dT%H%M%SZ")
    tasks = {t["field_id"]: t["task"] for t in representative_tasks(report) if t["kind"] == "retention"}

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Minima//Data Minimiser//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_esc('Deletion deadlines — ' + report.form.name)}",
    ]

    for row in report.rows:
        if not row.delete_by:
            continue
        start = date.fromisoformat(row.delete_by)
        # DTEND is exclusive for an all-day event: same day here would render as zero-length.
        end = start + timedelta(days=1)
        desc = [tasks.get(row.field_id) or f"Delete the data collected in “{row.label}”."]
        if row.retention_days:
            desc.append(f"Retention: {row.retention_days} days.")
        if row.kb_titles:
            desc.append("Legal basis: " + "; ".join(row.kb_titles))
        desc.append(f"Form: {report.form.name} · field: {row.field_id}")

        lines += [
            "BEGIN:VEVENT",
            f"UID:{_esc(sid or report.form.form_id)}-{_esc(row.field_id)}@minima",
            f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{start.strftime('%Y%m%d')}",
            f"DTEND;VALUE=DATE:{end.strftime('%Y%m%d')}",
            f"SUMMARY:{_esc(f'Delete “{row.label}” — {report.form.name}')}",
            f"DESCRIPTION:{_esc(' '.join(desc))}",
            "CATEGORIES:DATA-RETENTION",
            "TRANSP:TRANSPARENT",
            "BEGIN:VALARM",
            "ACTION:DISPLAY",
            f"TRIGGER:-P{max(1, reminder_days)}D",
            f"DESCRIPTION:{_esc(f'“{row.label}” has to be deleted in {max(1, reminder_days)} days.')}",
            "END:VALARM",
            "END:VEVENT",
        ]

    lines.append("END:VCALENDAR")

    folded: list[str] = []
    for line in lines:
        folded += _fold(line)
    # CRLF, always: Outlook rejects bare LF.
    return "\r\n".join(folded) + "\r\n"


def n_deadlines(report: Report) -> int:
    return sum(1 for r in report.rows if r.delete_by)
