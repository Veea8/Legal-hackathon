"""Compliance checks: deterministic legal invariants, no AI.

Each check may raise the *floor* (the mildest acceptable action) for a field. The merge never proposes
anything milder than the floor; the AI may only suggest a milder action, which the human can accept.
See docs/ARCHITECTURE.md section 5 for the table.
"""

from __future__ import annotations

from app.kb.categories import CategoryGroup, is_special_or_criminal, normalise_category
from app.models import Action, CheckResult, FieldSpec, FormSchema, Modifier, TriggeredRule, stricter

RETENTION_MAX_DAYS = 3650
RETENTION_MAX_DAYS_SENSITIVE = 1825

_DERIVED_SENSITIVE = {
    CategoryGroup.SPECIAL, CategoryGroup.CRIMINAL, CategoryGroup.ADJACENT,
    CategoryGroup.IDENTITY_DOC, CategoryGroup.FINANCIAL, CategoryGroup.BEHAVIOURAL,
}


def effective_sensitive(field: FieldSpec, group: CategoryGroup) -> bool:
    if field.sensitive is not None:
        return field.sensitive
    return group in _DERIVED_SENSITIVE


def check_field(form: FormSchema, field: FieldSpec) -> CheckResult:
    group, known = normalise_category(
        field.data_category, field_name=field.name, label=field.label, field_type=field.type
    )
    sensitive = effective_sensitive(field, group)
    has_purpose = field.has_purpose
    entry = form.stage == "entry"
    t: list[TriggeredRule] = []

    if not known:
        t.append(TriggeredRule(
            rule_id="C00", severity="info", floor_action=Action.keep,
            message=f"Data category not recognised; treated as {group.value.lower()} from the label. Confirm it in the grid.",
        ))

    if not field.required and not sensitive:
        t.append(TriggeredRule(
            rule_id="C01", severity="info", floor_action=Action.keep, kb_refs=["gdpr-25-2", "fadp-7"],
            message="Optional, low-risk field. Optional inclusive fields are not penalised.",
        ))

    if is_special_or_criminal(group) and not has_purpose:
        law = "gdpr-10" if group == CategoryGroup.CRIMINAL else "gdpr-9"
        t.append(TriggeredRule(
            rule_id="C02", severity="block", floor_action=Action.remove,
            alternative_action=Action.better_explain,
            modifiers=[Modifier.delay] if entry else [],
            kb_refs=[law, "gdpr-5-1-c", "fadp-5-c", "fadp-6-3"],
            message=("Special-category" if group == CategoryGroup.SPECIAL else "Criminal-offence")
            + " data without a documented purpose must not be collected"
            + (" at this early stage." if entry else "."),
        ))

    if is_special_or_criminal(group) and has_purpose:
        t.append(TriggeredRule(
            rule_id="C03", severity="info", floor_action=Action.keep,
            kb_refs=["gdpr-9-2", "gdpr-13", "fadp-6-7", "fadp-19"],
            message="Special-category data with a stated purpose: make sure an explicit legal basis exists and the purpose is explained to the person.",
        ))

    if field.required and not has_purpose:
        t.append(TriggeredRule(
            rule_id="C04", severity="warn", floor_action=Action.make_optional,
            kb_refs=["gdpr-5-1-c", "gdpr-25-2", "fadp-6-2", "fadp-7"],
            message="Mandatory field without a documented purpose. Mandatory is not the default; it needs a reason.",
        ))

    if not field.required and sensitive and not has_purpose:
        t.append(TriggeredRule(
            rule_id="C05", severity="warn", floor_action=Action.better_explain,
            kb_refs=["gdpr-13", "fadp-19"],
            message="Optional but sensitive field without an explanation. People must be told why it is asked and that it is voluntary.",
        ))

    if field.third_party_shared and not has_purpose:
        t.append(TriggeredRule(
            rule_id="C06", severity="warn", floor_action=Action.better_explain,
            kb_refs=["gdpr-13-1-e", "fadp-19"],
            message="Shared with a third party without a documented purpose. Recipients must be named at collection.",
        ))

    if group == CategoryGroup.IDENTITY_DOC and field.type == "file" and not has_purpose:
        t.append(TriggeredRule(
            rule_id="C07", severity="block", floor_action=Action.remove,
            alternative_action=Action.better_explain,
            kb_refs=["gdpr-5-1-c", "gdpr-32", "fadp-8"],
            message="Identity document upload without a documented need. High-risk data; collect only where legally required and say why.",
        ))

    rd = field.retention_days
    if rd is not None and (rd > RETENTION_MAX_DAYS or (sensitive and rd > RETENTION_MAX_DAYS_SENSITIVE)):
        t.append(TriggeredRule(
            rule_id="C08", severity="warn" if rd > RETENTION_MAX_DAYS else "info", floor_action=Action.keep,
            kb_refs=["gdpr-5-1-e", "fadp-6-4"],
            message=f"Retention of {rd} days ({rd / 365:.1f} years) for {'sensitive ' if sensitive else ''}data. Verify it against a legal retention duty; otherwise shorten.",
        ))

    if (group == CategoryGroup.BEHAVIOURAL or field.type == "oauth") and not has_purpose:
        t.append(TriggeredRule(
            rule_id="C09", severity="block", floor_action=Action.remove,
            modifiers=[Modifier.delay],
            kb_refs=["gdpr-7-4", "gdpr-5-1-c", "gdpr-25"],
            message="Access to behavioural data or an integration requested without a purpose. Premature at this stage and risks bundled consent.",
        ))

    if group == CategoryGroup.ADJACENT and field.required and not has_purpose:
        t.append(TriggeredRule(
            rule_id="C10", severity="warn", floor_action=Action.make_optional,
            alternative_action=Action.remove,
            kb_refs=["gdpr-5-1-c", "fadp-6-2"],
            message="Identity-related field made mandatory without a purpose. At most optional, with inclusive options and 'prefer not to say'.",
        ))

    floor = Action.keep
    for r in t:
        floor = stricter(floor, r.floor_action)
    return CheckResult(
        field_id=field.field_id,
        triggered=t,
        floor_action=floor,
        protected_inclusive=any(r.rule_id == "C01" for r in t),
    )


def run_checks(form: FormSchema) -> list[CheckResult]:
    return [check_field(form, f) for f in form.fields]


def check_alternative(result: CheckResult) -> Action | None:
    """Alternative action proposed by the strictest triggered rule, if any."""
    best = None
    for r in result.triggered:
        if r.floor_action == result.floor_action and r.alternative_action:
            best = r.alternative_action
    return best


def check_modifiers(result: CheckResult) -> list[Modifier]:
    mods: list[Modifier] = []
    for r in result.triggered:
        if r.floor_action == result.floor_action:
            for m in r.modifiers:
                if m not in mods:
                    mods.append(m)
    return mods
