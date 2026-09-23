"""Merge compliance checks and AI assessments into reviewable FieldRules, and apply human decisions.

Rules (docs/ARCHITECTURE.md section 7):
1. AI missing            -> action = floor, source = checks
2. AI action >= floor    -> action = AI action, modifiers = AI's (check modifiers only if the AI gave none
                            and matched the floor), source = both / ai
3. AI action <  floor    -> action = floor, AI's milder action becomes `ai_milder_suggestion`, disagreement = true
4. alternative = AI alternative or check alternative; reason = AI reason else check message; kb_refs = union
5. Human override below the floor -> warning + note required; recorded as flagged owner decision
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from app.checks.rules import check_alternative, check_modifiers
from app.kb import filter_known
from app.models import (
    Action,
    AIAssessment,
    CheckResult,
    FieldRule,
    FieldSpec,
    FormSchema,
    HumanOverride,
    MilderSuggestion,
    Modifier,
    RuleOverride,
    RuleSet,
    is_milder,
)


class OverrideError(ValueError):
    """Raised when a human decision is not allowed as given (e.g. missing note)."""


def _check_reason(check: CheckResult) -> str:
    msgs = [t.message for t in check.triggered if t.floor_action == check.floor_action and t.severity != "info"]
    if not msgs:
        msgs = [t.message for t in check.triggered if t.rule_id in ("C01", "C03")] or ["No compliance issue found."]
    return " ".join(msgs)


def _check_refs(check: CheckResult) -> list[str]:
    out: list[str] = []
    for t in check.triggered:
        for r in t.kb_refs:
            if r not in out:
                out.append(r)
    return out


def _data_handling(action: Action, ai: Optional[AIAssessment]) -> str:
    if action == Action.remove:
        return "delete"
    if ai is not None:
        return ai.data_handling
    return "retain"


def merge_field(
    field: FieldSpec,
    check: CheckResult,
    ai: Optional[AIAssessment],
    *,
    ai_error: Optional[str] = None,
) -> FieldRule:
    floor = check.floor_action
    c_alt = check_alternative(check)
    c_mods = check_modifiers(check)
    c_refs = _check_refs(check)

    if ai is None:
        rule = FieldRule(
            field_id=field.field_id,
            action=floor,
            proposed_action=floor,
            modifiers=c_mods,
            alternative_action=c_alt if c_alt != floor else None,
            source="checks",
            check=check,
            ai=None,
            reason=_check_reason(check),
            kb_refs=c_refs,
            retention_days=field.retention_days,
            data_handling=_data_handling(floor, None),  # type: ignore[arg-type]
            warning="AI assessment unavailable; the compliance check result stands." if ai_error else None,
        )
        return rule

    ai_refs = filter_known(ai.kb_refs)
    refs = list(dict.fromkeys(ai_refs + c_refs))
    retention = ai.retention_suggestion_days if ai.retention_suggestion_days is not None else field.retention_days

    if not is_milder(ai.proposed_action, floor):
        # AI agrees with or exceeds the floor: it owns the nuance (e.g. "delay" vs outright removal).
        # Check modifiers only fill in when the AI matched the floor without saying how.
        action = ai.proposed_action
        alt = ai.alternative_action or c_alt
        mods = list(ai.modifiers) if (ai.modifiers or action != floor) else list(c_mods)
        return FieldRule(
            field_id=field.field_id,
            action=action,
            proposed_action=action,
            modifiers=mods,
            alternative_action=alt if alt and alt != action else None,
            source="both" if floor != Action.keep else "ai",
            check=check,
            ai=ai,
            disagreement=False,
            reason=ai.reason,
            kb_refs=refs,
            microcopy=ai.microcopy,
            suggested_label=ai.suggested_label,
            retention_days=retention,
            data_handling=_data_handling(action, ai),  # type: ignore[arg-type]
        )

    # AI milder than the compliance floor: floor wins, AI view is offered as a suggestion.
    return FieldRule(
        field_id=field.field_id,
        action=floor,
        proposed_action=floor,
        modifiers=c_mods,
        alternative_action=c_alt if c_alt and c_alt != floor else None,
        source="checks",
        check=check,
        ai=ai,
        disagreement=True,
        ai_milder_suggestion=MilderSuggestion(action=ai.proposed_action, justification=ai.reason),
        reason=_check_reason(check),
        kb_refs=refs,
        microcopy=ai.microcopy,
        suggested_label=ai.suggested_label,
        retention_days=retention,
        data_handling=_data_handling(floor, ai),  # type: ignore[arg-type]
    )


def build_ruleset(
    form: FormSchema,
    checks: list[CheckResult],
    assessments: dict[str, Optional[AIAssessment]],
    *,
    ai_model: Optional[str],
    ai_errors: Optional[dict[str, str]] = None,
    cached: bool = False,
    status: str = "proposed",
) -> RuleSet:
    ai_errors = ai_errors or {}
    by_id = {c.field_id: c for c in checks}
    rules = [
        merge_field(f, by_id[f.field_id], assessments.get(f.field_id), ai_error=ai_errors.get(f.field_id))
        for f in form.fields
    ]
    return RuleSet(
        form_id=form.form_id,
        status=status,  # type: ignore[arg-type]
        rules=rules,
        fields_done=len(form.fields),
        fields_total=len(form.fields),
        ai_model=ai_model,
        cached=cached,
        computed_at=datetime.now(timezone.utc),
        ai_errors=ai_errors,
    )


def _flag_text(check: CheckResult) -> str:
    ids = [t.rule_id for t in check.triggered if t.floor_action == check.floor_action and t.severity != "info"]
    return ", ".join(ids) if ids else "compliance check"


def _apply_retention(rule: FieldRule, o: RuleOverride) -> None:
    """A deletion deadline set by the human. `expire` marks the field as time-limited in the report."""
    if o.clear_retention:
        rule.retention_days = None
        if rule.data_handling == "expire":
            rule.data_handling = "delete" if rule.action == Action.remove else "retain"
    elif o.retention_days is not None:
        rule.retention_days = o.retention_days
        if rule.action != Action.remove:
            rule.data_handling = "expire"


def apply_overrides(ruleset: RuleSet, overrides: list[RuleOverride]) -> RuleSet:
    """Apply human decisions in place and return the ruleset. Raises OverrideError on invalid input."""
    for o in overrides:
        rule = ruleset.rule(o.field_id)
        if rule is None:
            raise OverrideError(f"Unknown field '{o.field_id}'")
        floor = rule.check.floor_action
        retention_touched = o.clear_retention or o.retention_days is not None

        if o.accept_ai_suggestion:
            if rule.ai_milder_suggestion is None:
                raise OverrideError(f"No AI suggestion to accept for '{o.field_id}'")
            new_action = rule.ai_milder_suggestion.action
            note = o.note or f"Accepted AI suggestion: {rule.ai_milder_suggestion.justification}"
            below_floor_warning = (
                f"AI suggestion accepted below the compliance floor ('{new_action.value}' instead of "
                f"'{floor.value}', {_flag_text(rule.check)}). Justification: {rule.ai_milder_suggestion.justification}"
            )
        elif o.accept_alternative:
            if rule.alternative_action is None:
                raise OverrideError(f"No alternative action for '{o.field_id}'")
            new_action = rule.alternative_action
            note = o.note or "Accepted alternative action"
            below_floor_warning = (
                f"Alternative accepted below the compliance floor ('{new_action.value}' instead of "
                f"'{floor.value}', {_flag_text(rule.check)}). Keep the field only with a documented purpose "
                f"and a clear explanation to the person."
            )
        elif o.action is not None:
            new_action = o.action
            note = o.note
            if is_milder(new_action, floor) and not note.strip():
                raise OverrideError(
                    f"'{o.field_id}': choosing '{new_action.value}' is milder than the compliance floor "
                    f"'{floor.value}'. A note explaining the decision is required."
                )
            below_floor_warning = (
                f"Owner keeps a field the compliance check flags ({_flag_text(rule.check)}): "
                f"'{new_action.value}' is milder than the floor '{floor.value}'."
            )
        elif retention_touched:
            # deadline only: the action stands as it is
            _apply_retention(rule, o)
            continue
        else:
            # reset to the merged proposal
            rule.action = rule.proposed_action
            rule.human_override = None
            rule.warning = None
            rule.source = "checks" if rule.ai is None or rule.disagreement else ("both" if floor != Action.keep else "ai")
            continue

        rule.action = new_action
        rule.human_override = HumanOverride(action=new_action, note=note)
        rule.source = "human"
        rule.warning = below_floor_warning if is_milder(new_action, floor) else None
        rule.data_handling = "delete" if new_action == Action.remove else (
            rule.ai.data_handling if rule.ai else "retain"
        )
        _apply_retention(rule, o)
    ruleset.status = "reviewed"
    return ruleset
