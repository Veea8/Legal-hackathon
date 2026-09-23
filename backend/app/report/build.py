"""Report for the data-collection owner: what changes, why, with legal references and flagged decisions."""

from __future__ import annotations

import csv
import html
import io
from datetime import datetime, timedelta, timezone

from app.kb import kb_refs, kb_titles
from app.kb.categories import is_special_or_criminal, normalise_category
from app.models import (
    Action,
    FormSchema,
    MinimisedForm,
    Report,
    ReportFormInfo,
    ReportRow,
    ReportSummary,
    RetentionRow,
    RuleSet,
)


def _owner_decision(rule) -> str:
    if rule.human_override is None:
        return "accepted proposal"
    note = f" — {rule.human_override.note}" if rule.human_override.note else ""
    if rule.human_override.action == rule.proposed_action:
        return f"confirmed {rule.action.value}{note}"
    return f"override: {rule.proposed_action.value} → {rule.action.value}{note}"


def _delete_by(rule, generated_at: datetime) -> str | None:
    """A field with a retention period must be deleted by this date. Removed fields are not collected at all."""
    if rule.action == Action.remove or rule.retention_days is None:
        return None
    return (generated_at.date() + timedelta(days=rule.retention_days)).isoformat()


def build_report(schema: FormSchema, ruleset: RuleSet, minimised: MinimisedForm) -> Report:
    generated_at = datetime.now(timezone.utc)
    rows: list[ReportRow] = []
    counts: dict[str, int] = {a.value: 0 for a in Action}
    n_special = 0
    n_flagged = 0
    principles: list[str] = []
    retention: list[RetentionRow] = []

    for field in schema.fields:
        rule = ruleset.rule(field.field_id)
        if rule is None:
            continue
        group, _ = normalise_category(field.data_category, field_name=field.name, label=field.label, field_type=field.type)
        if is_special_or_criminal(group) or (rule.ai is not None and rule.ai.special_category):
            n_special += 1
        if rule.warning and rule.human_override is not None:
            n_flagged += 1
        counts[rule.action.value] += 1
        for r in rule.kb_refs:
            if r not in principles:
                principles.append(r)
        rows.append(ReportRow(
            field_id=field.field_id,
            label=field.label,
            original_required=field.required,
            original_category=field.data_category,
            action=rule.action,
            modifiers=list(rule.modifiers),
            reason=rule.reason,
            kb_refs=list(rule.kb_refs),
            kb_titles=kb_titles(rule.kb_refs),
            source=rule.source,
            owner_decision=_owner_decision(rule),
            warning=rule.warning,
            retention_days=rule.retention_days,
            delete_by=_delete_by(rule, generated_at),
            data_handling=rule.data_handling,
        ))
        c08 = any(t.rule_id == "C08" for t in rule.check.triggered)
        if c08 or (rule.retention_days is not None and rule.retention_days != field.retention_days):
            retention.append(RetentionRow(
                field_id=field.field_id, label=field.label,
                current_days=field.retention_days, suggested_days=rule.retention_days,
            ))

    no_longer = [r.label for r in minimised.removed] + [d.label for d in minimised.delayed]
    return Report(
        form=ReportFormInfo(
            form_id=schema.form_id, name=schema.name,
            business_context=schema.business_context, jurisdiction=schema.jurisdiction,
        ),
        summary=ReportSummary(
            n_fields=len(rows), counts=counts, n_special_category=n_special,
            n_overrides_flagged=n_flagged, n_ai_unavailable=len(ruleset.ai_errors),
        ),
        rows=rows,
        no_longer_collected=no_longer,
        retention_table=retention,
        principles=principles,
        ai_model=ruleset.ai_model,
        cached=ruleset.cached,
        generated_at=generated_at,
    )


def render_csv(report: Report) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["field_id", "label", "original_required", "original_category", "action", "modifiers",
                "reason", "legal_refs", "source", "owner_decision", "warning", "retention_days",
                "delete_by", "data_handling"])
    for r in report.rows:
        w.writerow([r.field_id, r.label, "Y" if r.original_required else "N", r.original_category or "",
                    r.action.value, "+".join(m.value for m in r.modifiers), r.reason, "; ".join(r.kb_titles),
                    r.source, r.owner_decision, r.warning or "", r.retention_days or "",
                    r.delete_by or "", r.data_handling])
    return buf.getvalue()


_ACTION_LABEL = {
    "keep": "Keep", "better_explain": "Add explanation", "make_optional": "Make optional", "remove": "Remove",
}

# What the person responsible actually has to go and do. `keep` produces no task by design:
# the report's value is the short list of changes, not a restatement of the whole form.
_TASK = {
    "remove": "Delete this field from the form. Stop collecting it.",
    "make_optional": "Remove the required flag. The form must submit with this left blank.",
    "better_explain": "Add one sentence under the field: why you ask, and what happens with the answer.",
}

_MODIFIER_TASK = {
    "delay": "Ask for it later in the journey, not at first contact.",
    "role_based": "Ask only the roles or cases that genuinely need it.",
    "conditional_on_purpose": "Do not ask until a purpose is written down.",
}


def pretty_date(iso: str) -> str:
    try:
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%d %B %Y").lstrip("0")
    except ValueError:
        return iso


def _change_task(r) -> str:
    mods = {m.value for m in r.modifiers}
    # "remove" + "delay" is the jury's remove_or_delay: out of this form, not out of the product.
    # Saying "stop collecting it" and "ask for it later" in the same breath reads as a contradiction.
    if r.action.value == "remove" and "delay" in mods:
        return ("Take this field out of this form. If you genuinely need it, ask for it later in the "
                "journey, once there is a reason the person can see.")
    extra = " ".join(_MODIFIER_TASK[m] for m in ("delay", "role_based", "conditional_on_purpose") if m in mods)
    return _TASK[r.action.value] + (f" {extra}" if extra else "")


def representative_tasks(report: Report) -> list[dict[str, str]]:
    """The action list for the data protection representative / form owner, in priority order."""
    tasks: list[dict[str, str]] = []
    for r in report.rows:
        if r.action.value in _TASK:
            tasks.append({
                "label": r.label,
                "field_id": r.field_id,
                "action": r.action.value,
                "task": _change_task(r),
                "kind": "change",
            })
    for r in report.rows:
        if r.delete_by:
            tasks.append({
                "label": r.label,
                "field_id": r.field_id,
                "action": "expire",
                "task": f"Set up deletion after {r.retention_days} days. Data collected today has to be deleted by {pretty_date(r.delete_by)}.",
                "kind": "retention",
            })
    for r in report.rows:
        if r.warning:
            tasks.append({
                "label": r.label,
                "field_id": r.field_id,
                "action": "signoff",
                "task": f"Sign off in writing: {r.warning}",
                "kind": "signoff",
            })
    return tasks


TASK_BADGE = {
    "remove": "Remove", "make_optional": "Make optional", "better_explain": "Add explanation",
    "expire": "Deletion deadline", "signoff": "Needs sign-off",
}

_JURISDICTION_LABEL = {
    "both": "EU (GDPR) + Switzerland (revFADP)", "eu": "EU (GDPR)", "ch": "Switzerland (revFADP)",
}


def _refs_html(ids: list[str]) -> str:
    """Legal references as real links to the article text."""
    e = html.escape
    parts = [
        f"<a href='{e(url)}' target='_blank' rel='noreferrer'>{e(cite)}</a> <span class='sub'>{e(title)}</span>"
        if url else f"{e(cite)} <span class='sub'>{e(title)}</span>"
        for cite, title, url in kb_refs(ids)
    ]
    return "<div class='ref'>" + "</div><div class='ref'>".join(parts) + "</div>" if parts else "&ndash;"


def render_html(report: Report) -> str:
    e = html.escape
    s = report.summary
    tasks = representative_tasks(report)

    rows = "".join(
        f"<tr class='{'todo t-' + r.action.value if r.action.value != 'keep' else ''}'>"
        f"<td><b>{e(r.label)}</b><div class='sub'>{e(r.field_id)} &middot; "
        f"{'required' if r.original_required else 'optional'}"
        f"{' &middot; ' + e(r.original_category) if r.original_category else ''}</div></td>"
        f"<td><span class='pill p-{r.action.value}'>{_ACTION_LABEL[r.action.value]}</span>"
        f"{('<div class=sub>+ ' + e(', '.join(m.value for m in r.modifiers)) + '</div>') if r.modifiers else ''}"
        f"{('<div class=sub>Delete by ' + e(pretty_date(r.delete_by)) + '</div>') if r.delete_by else ''}</td>"
        f"<td>{e(r.reason)}"
        f"{('<div class=warn>' + e(r.warning) + '</div>') if r.warning else ''}</td>"
        f"<td class='sub'>{_refs_html(r.kb_refs) }</td>"
        f"<td class='sub'>{e(r.owner_decision)}</td>"
        f"</tr>"
        for r in report.rows
    )

    nlc = "".join(f"<li>{e(x)}</li>" for x in report.no_longer_collected) or "<li class='sub'>None &mdash; every field stays.</li>"

    deadline_rows = "".join(
        f"<tr><td>{e(r.label)}</td><td>{r.retention_days} days</td><td><b>{e(pretty_date(r.delete_by))}</b></td></tr>"
        for r in report.rows if r.delete_by
    ) or "<tr><td colspan='3' class='sub'>No deletion deadline set for any field.</td></tr>"

    def _task_li(t: dict[str, str]) -> str:
        return (
            f"<li class='task k-{t['kind']}'>"
            f"<span class='chk' aria-hidden='true'></span>"
            f"<span class='t-body'><span class='t-head'><b>{e(t['label'])}</b>"
            f"<span class='pill p-{t['action']}'>{TASK_BADGE[t['action']]}</span></span>"
            f"<span class='t-do'>{e(t['task'])}</span></span></li>"
        )

    # Changing the form, scheduling deletion and signing off are three different jobs, often for
    # three different people. A flat list of eleven reads as noise; three short lists read as work.
    task_items = ""
    for kind, heading in (
        ("change", "Change the form"),
        ("retention", "Set up deletion"),
        ("signoff", "Sign off in writing"),
    ):
        group = [t for t in tasks if t["kind"] == kind]
        if not group:
            continue
        task_items += f"<li class='t-group'>{heading} <span class='sub'>({len(group)})</span></li>"
        task_items += "".join(_task_li(t) for t in group)
    task_items = task_items or "<li class='sub'>Nothing to change &mdash; every field survived the review as it is.</li>"

    counts = "".join(
        f"<div class='stat'><div class='stat-n'>{v}</div><div class='stat-l'>{_ACTION_LABEL[k]}</div></div>"
        for k, v in s.counts.items()
    )

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Data minimisation report &ndash; {e(report.form.name)}</title>
<style>
:root{{--ink:#12141a;--muted:#6b7280;--line:#e5e7eb;--bg:#fff;--accent:#4f46e5}}
*{{box-sizing:border-box}}
body{{font-family:ui-sans-serif,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;max-width:60rem;
margin:0 auto;padding:3rem 1.5rem;color:var(--ink);background:var(--bg);line-height:1.5;font-size:15px}}
h1{{font-size:1.75rem;margin:0 0 .25rem;letter-spacing:-.02em}}
h2{{font-size:1.05rem;margin:2.5rem 0 .75rem;letter-spacing:-.01em}}
.lede{{color:var(--muted);margin:0 0 2rem}}
.stats{{display:flex;gap:.5rem;flex-wrap:wrap;margin:1.5rem 0}}
.stat{{flex:1 1 7rem;border:1px solid var(--line);border-radius:10px;padding:.75rem .9rem}}
.stat-n{{font-size:1.5rem;font-weight:650;letter-spacing:-.02em}}
.stat-l{{font-size:.75rem;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}}
table{{border-collapse:collapse;width:100%;margin:.5rem 0;font-size:.85rem}}
th{{text-align:left;font-size:.7rem;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);
padding:.5rem .6rem;border-bottom:1px solid var(--line)}}
td{{padding:.7rem .6rem;border-bottom:1px solid var(--line);vertical-align:top}}
.sub{{color:var(--muted);font-size:.78rem}}
.pill{{display:inline-block;font-size:.75rem;font-weight:600;padding:.15rem .5rem;border-radius:999px;
border:1px solid var(--line);white-space:nowrap}}
.p-remove{{color:#9f1239;background:#fff1f2;border-color:#fecdd3}}
.p-make_optional{{color:#92400e;background:#fffbeb;border-color:#fde68a}}
.p-better_explain{{color:#3730a3;background:#eef2ff;border-color:#c7d2fe}}
.p-keep{{color:#374151;background:#f9fafb;border-color:#e5e7eb}}
.warn{{margin-top:.35rem;background:#fffbeb;border-left:3px solid #f59e0b;padding:.3rem .5rem;font-size:.78rem}}
.p-expire{{color:#0f766e;background:#effaf7;border-color:#bfe6dd}}
.p-signoff{{color:#c2410c;background:#fff7ed;border-color:#fed7aa}}
a{{color:var(--accent)}}
.ref{{margin:.15rem 0;line-height:1.35}}
.ref a{{font-weight:600;text-decoration:none;border-bottom:1px solid currentColor;white-space:nowrap}}
table.fields{{table-layout:fixed}}
/* The hand-over list is the point of the report, so it gets the only box on the page. */
.actions{{border:2px solid var(--ink);border-radius:14px;padding:1.1rem 1.25rem 1.25rem;margin:2rem 0 0;
background:#fcfcfd}}
.actions .a-head{{margin:0;font-size:1.1rem}}
.actions .a-lede{{margin:.25rem 0 .9rem}}
.tasks{{list-style:none;padding:0;margin:0}}
.task{{display:flex;gap:.7rem;align-items:flex-start;padding:.65rem 0;border-top:1px solid var(--line)}}
.task:first-child{{border-top:none}}
.t-group{{font-size:.7rem;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);
font-weight:700;padding:.9rem 0 .3rem;border-top:1px solid var(--line)}}
.t-group:first-child{{border-top:none;padding-top:.2rem}}
.t-group + .task{{border-top:none}}
.chk{{flex:none;width:1.05rem;height:1.05rem;margin-top:.15rem;border:1.5px solid #9ca3af;border-radius:4px}}
.t-body{{display:block}}
.t-head{{display:flex;gap:.45rem;align-items:center;flex-wrap:wrap}}
.t-do{{display:block;font-size:.85rem;color:#374151;margin-top:.15rem}}
tr.todo td:first-child{{box-shadow:inset 3px 0 0 -1px currentColor}}
tr.t-remove td:first-child{{color:#9f1239}}
tr.t-make_optional td:first-child{{color:#92400e}}
tr.t-better_explain td:first-child{{color:#3730a3}}
@media print{{.actions{{break-inside:avoid}}}}
ul{{padding-left:1.1rem;margin:.4rem 0}} li{{margin:.2rem 0}}
footer{{margin-top:3rem;padding-top:1rem;border-top:1px solid var(--line);color:var(--muted);font-size:.78rem}}
@media print{{body{{padding:0;max-width:none}} .stat{{break-inside:avoid}} tr{{break-inside:avoid}}}}
</style></head><body>
<h1>Data minimisation report</h1>
<p class="lede"><b>{e(report.form.name)}</b> &mdash; {e(report.form.business_context)}<br>
{e(_JURISDICTION_LABEL.get(report.form.jurisdiction, report.form.jurisdiction))} &middot;
generated {report.generated_at:%d %B %Y, %H:%M} UTC &middot;
AI: {e(report.ai_model or 'unavailable')}{' (cached)' if report.cached else ''}</p>

<div class="stats">{counts}
<div class="stat"><div class="stat-n">{s.n_special_category}</div><div class="stat-l">Special category</div></div>
<div class="stat"><div class="stat-n">{s.n_overrides_flagged}</div><div class="stat-l">Flagged decisions</div></div>
</div>

<section class="actions">
<h2 class="a-head">Actions for the data protection representative</h2>
<p class="sub a-lede">{len(tasks)} thing{'' if len(tasks) == 1 else 's'} to do. Everything below is already
decided &mdash; this is the hand-over list. Fields not listed here stay exactly as they are.</p>
<ul class="tasks">{task_items}</ul>
</section>

<h2>Stop collecting these fields</h2>
<ul>{nlc}</ul>

<h2>Deletion deadlines</h2>
<table><thead><tr><th>Field</th><th>Kept for</th><th>Has to be deleted by</th></tr></thead>
<tbody>{deadline_rows}</tbody></table>

<h2>Decision per field</h2>
<table class="fields">
<colgroup><col style="width:17%"><col style="width:13%"><col style="width:32%"><col style="width:26%"><col style="width:12%"></colgroup>
<thead><tr><th>Field</th><th>Decision</th><th>Why</th><th>Legal reference</th><th>Owner</th></tr></thead>
<tbody>{rows}</tbody></table>

<h2>Principles applied</h2>
<p class="sub">{e(', '.join(kb_titles(report.principles))) or 'none'}</p>

<footer>Generated by Minima. Compliance checks are deterministic; the AI assessment only ever saw
field names, labels and purposes, never data values. A human reviewed every decision. This is not legal advice.</footer>
</body></html>"""
