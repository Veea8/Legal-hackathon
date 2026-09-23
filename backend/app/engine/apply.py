"""Minimisation engine: applies a reviewed RuleSet to a FormSchema. Deterministic, no AI.

remove            -> field dropped (or moved to "collect later" when the rule carries `delay` / `role_based`)
make_optional     -> required = False (+ microcopy / label if provided)
better_explain    -> unchanged requirement, microcopy attached (fallback generated from the purpose text)
keep              -> unchanged (+ microcopy if the AI offered one)
"""

from __future__ import annotations

from app.models import (
    Action,
    DelayedField,
    Diff,
    FieldRule,
    FieldSpec,
    FormSchema,
    MinimisedField,
    MinimisedForm,
    Modifier,
    RemovedField,
    RuleSet,
)


def fallback_microcopy(field: FieldSpec) -> str:
    if field.has_purpose:
        purpose = field.purpose_text.strip().rstrip(".")  # type: ignore[union-attr]
        return f"We ask for this to {purpose[0].lower() + purpose[1:]}."
    return "Tell people in one sentence why this is asked and what happens with it."


def _delay_note(rule: FieldRule) -> str:
    if Modifier.role_based in rule.modifiers:
        return "Collect only for the specific roles or cases that need it, at that point."
    return "Collect at a later stage, once there is a documented purpose and the person is informed."


def _minimised_field(field: FieldSpec, rule: FieldRule, *, required: bool, microcopy: str | None) -> MinimisedField:
    data = field.model_dump()
    data.update(
        required=required,
        label=rule.suggested_label or field.label,
        retention_days=rule.retention_days if rule.retention_days is not None else field.retention_days,
    )
    return MinimisedField(**data, microcopy=microcopy, action=rule.action, modifiers=list(rule.modifiers))


def apply(schema: FormSchema, ruleset: RuleSet) -> MinimisedForm:
    out = MinimisedForm(form_id=schema.form_id, name=schema.name)
    diff = Diff()
    for field in schema.fields:
        rule = ruleset.rule(field.field_id)
        if rule is None:
            out.fields.append(MinimisedField(**field.model_dump()))
            diff.unchanged.append(field.field_id)
            continue

        action = rule.action
        if action == Action.remove:
            if Modifier.delay in rule.modifiers or Modifier.role_based in rule.modifiers:
                out.delayed.append(DelayedField(field_id=field.field_id, label=field.label, note=_delay_note(rule)))
                diff.delayed.append(field.field_id)
            else:
                out.removed.append(RemovedField(field_id=field.field_id, label=field.label, reason=rule.reason))
                diff.removed.append(field.field_id)
            continue

        if action == Action.make_optional:
            out.fields.append(_minimised_field(field, rule, required=False, microcopy=rule.microcopy))
            diff.made_optional.append(field.field_id)
        elif action == Action.better_explain:
            out.fields.append(_minimised_field(
                field, rule, required=field.required, microcopy=rule.microcopy or fallback_microcopy(field)
            ))
            diff.explained.append(field.field_id)
        else:  # keep
            out.fields.append(_minimised_field(field, rule, required=field.required, microcopy=rule.microcopy))
            diff.unchanged.append(field.field_id)
    out.diff = diff
    return out
