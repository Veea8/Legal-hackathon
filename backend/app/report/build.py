"""Report for the data-collection owner: what changes, why, with legal references and flagged decisions."""

from __future__ import annotations

import csv
import html
import io
from datetime import datetime, timezone

from app.kb import kb_titles
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


def build_report(schema: FormSchema, ruleset: RuleSet, minimised: MinimisedForm) -> Report:
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
        generated_at=datetime.now(timezone.utc),
    )


def render_csv(report: Report) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["field_id", "label", "original_required", "original_category", "action", "modifiers",
                "reason", "legal_refs", "source", "owner_decision", "warning", "retention_days", "data_handling"])
    for r in report.rows:
        w.writerow([r.field_id, r.label, "Y" if r.original_required else "N", r.original_category or "",
                    r.action.value, "+".join(m.value for m in r.modifiers), r.reason, "; ".join(r.kb_titles),
                    r.source, r.owner_decision, r.warning or "", r.retention_days or "", r.data_handling])
    return buf.getvalue()


_ACTION_LABEL = {
    "keep": "Keep", "better_explain": "Better explain", "make_optional": "Make optional", "remove": "Remove",
}


def render_html(report: Report) -> str:
    e = html.escape
    s = report.summary
    rows = "".join(
        f"<tr class='a-{r.action.value}'><td>{e(r.label)}<br><small>{e(r.field_id)}</small></td>"
        f"<td>{'required' if r.original_required else 'optional'}<br><small>{e(r.original_category or '')}</small></td>"
        f"<td><b>{_ACTION_LABEL[r.action.value]}</b>{(' + ' + ', '.join(m.value for m in r.modifiers)) if r.modifiers else ''}</td>"
        f"<td>{e(r.reason)}</td><td><small>{e('; '.join(r.kb_titles))}</small></td>"
        f"<td>{e(r.owner_decision)}{('<br><mark>' + e(r.warning) + '</mark>') if r.warning else ''}</td></tr>"
        for r in report.rows
    )
    nlc = "".join(f"<li>{e(x)}</li>" for x in report.no_longer_collected) or "<li>none</li>"
    ret = "".join(
        f"<tr><td>{e(r.label)}</td><td>{r.current_days or '–'}</td><td>{r.suggested_days or '–'}</td></tr>"
        for r in report.retention_table
    ) or "<tr><td colspan=3>no retention changes</td></tr>"
    counts = " · ".join(f"{_ACTION_LABEL[k]}: {v}" for k, v in s.counts.items())
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Data minimisation report – {e(report.form.name)}</title>
<style>
body{{font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem;color:#111}}
table{{border-collapse:collapse;width:100%;margin:1rem 0}} td,th{{border:1px solid #ddd;padding:.5rem;vertical-align:top;text-align:left;font-size:.9rem}}
th{{background:#f3f3f3}} small{{color:#666}} mark{{background:#ffe8a3}}
tr.a-remove td:nth-child(3){{color:#b00020}} tr.a-make_optional td:nth-child(3){{color:#a05a00}} tr.a-better_explain td:nth-child(3){{color:#1a5fb4}}
@media print{{body{{margin:0}} a{{display:none}}}}
</style></head><body>
<h1>Data minimisation report</h1>
<p><b>{e(report.form.name)}</b> — {e(report.form.business_context)} · jurisdiction: {e(report.form.jurisdiction)}
· generated {report.generated_at:%Y-%m-%d %H:%M} UTC · AI: {e(report.ai_model or 'unavailable')}{' (cached)' if report.cached else ''}</p>
<p>{s.n_fields} fields · {counts} · special-category fields: {s.n_special_category} · flagged owner decisions: {s.n_overrides_flagged}</p>
<h2>Fields no longer collected in this form</h2><ul>{nlc}</ul>
<h2>Per-field decisions</h2>
<table><thead><tr><th>Field</th><th>Before</th><th>Action</th><th>Reason</th><th>Legal basis</th><th>Owner decision</th></tr></thead><tbody>{rows}</tbody></table>
<h2>Retention</h2><table><thead><tr><th>Field</th><th>Current days</th><th>Suggested days</th></tr></thead><tbody>{ret}</tbody></table>
<h2>Principles applied</h2><p>{e(', '.join(kb_titles(report.principles)))}</p>
<p><small>Generated by the Data Minimiser. Compliance checks are deterministic; the AI assessment only ever saw field names, labels and purposes, never data values. A human reviewed every decision. This is not legal advice.</small></p>
</body></html>"""
