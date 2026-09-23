"""AI assessment: one Apertus call per field, run concurrently, normalised into `AIAssessment`.

    assessments, errors = await assess_form(schema, client=None, on_field=None)
        assessments: {field_id: AIAssessment | None}
        errors:      {field_id: "short error text"}   (a failing field never fails the form)
        on_field(field_id, assessment_or_None, error_or_None) is called as each field finishes.

`client` only needs `complete_json(system, user)` and `model`; tests pass a fake. When the real client is not
configured, assess_form returns immediately with all-None and an error per field.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any, Awaitable, Callable, Optional

from app.ai.client import AIError, ai_available, ai_model_name, get_client, json_mode_supported  # noqa: F401
from app.ai.prompts import SYSTEM_PROMPT, field_prompt
from app.kb import filter_known, kb_prompt_lines
from app.models import Action, AIAssessment, FieldSpec, FormSchema, Modifier

OnField = Callable[[str, Optional[AIAssessment], Optional[str]], None]

_ACTIONS = {
    "keep": Action.keep, "retain": Action.keep, "ok": Action.keep, "keep_optional": Action.keep,
    "keep_as_is": Action.keep, "no_change": Action.keep, "unchanged": Action.keep,
    "better_explain": Action.better_explain, "explain": Action.better_explain, "clarify": Action.better_explain,
    "explain_better": Action.better_explain, "add_explanation": Action.better_explain,
    "make_optional": Action.make_optional, "optional": Action.make_optional, "make_voluntary": Action.make_optional,
    "remove": Action.remove, "delete": Action.remove, "drop": Action.remove, "do_not_collect": Action.remove,
}
_MODIFIERS = {
    "delay": Modifier.delay, "defer": Modifier.delay, "later": Modifier.delay, "postpone": Modifier.delay,
    "role_based": Modifier.role_based, "role": Modifier.role_based, "specific_roles": Modifier.role_based,
    "conditional_on_purpose": Modifier.conditional_on_purpose, "conditional": Modifier.conditional_on_purpose,
    "if_purpose_documented": Modifier.conditional_on_purpose,
}
_NECESSITY = {"necessary", "useful", "unnecessary", "unclear"}
_HANDLING = {
    "retain": "retain", "keep": "retain", "delete": "delete", "drop": "delete", "remove": "delete",
    "pseudonymise": "pseudonymise", "pseudonymize": "pseudonymise", "hash": "pseudonymise", "anonymise": "pseudonymise",
    "anonymize": "pseudonymise", "expire": "expire", "expiry": "expire", "time_limit": "expire",
}


def _key(v: Any) -> str:
    return re.sub(r"[\s\-]+", "_", str(v or "").strip().lower())


def _parse_action(v: Any) -> tuple[Optional[Action], list[Modifier], Optional[Action]]:
    """'remove_or_delay' -> (remove, [delay], None); 'make_optional_or_remove' -> (make_optional, [], remove)."""
    k = _key(v)
    if not k or k in ("null", "none"):
        return None, [], None
    action: Optional[Action] = None
    alt: Optional[Action] = None
    mods: list[Modifier] = []
    for tok in k.split("_or_"):
        if tok in _MODIFIERS and tok not in _ACTIONS:
            mods.append(_MODIFIERS[tok])
            if action is None:
                action = Action.remove  # "delay" alone means: do not collect now
            continue
        a = _ACTIONS.get(tok)
        if a is None:
            continue
        if action is None:
            action = a
        elif alt is None and a != action:
            alt = a
    return action, mods, alt


def _opt_str(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return None if not s or s.lower() in ("null", "none", "n/a") else s


def _opt_int(v: Any) -> Optional[int]:
    if v is None or isinstance(v, bool):
        return None
    m = re.search(r"-?\d+", str(v))
    return int(m.group()) if m else None


def _bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    return _key(v) in ("true", "yes", "y", "1")


def _confidence(v: Any) -> float:
    try:
        c = float(v)
    except (TypeError, ValueError):
        return 0.5
    if c > 1.0 and c <= 100.0:
        c /= 100.0
    return min(1.0, max(0.0, c))


def _refs(v: Any) -> list[str]:
    if isinstance(v, str):
        v = re.split(r"[,\s;]+", v)
    return filter_known([str(x).strip().lower() for x in (v or []) if str(x).strip()])


def normalise_assessment(field_id: str, raw: dict[str, Any]) -> AIAssessment:
    """Tolerant normalisation of a model reply, then pydantic validation."""
    raw = dict(raw or {})
    action, mods, alt_from_action = _parse_action(raw.get("proposed_action") or raw.get("action"))
    if action is None:
        raise AIError("reply has no recognisable proposed_action")
    alt = _parse_action(raw.get("alternative_action"))[0] or alt_from_action
    if alt == action:
        alt = None
    raw_mods = raw.get("modifiers") or []
    if isinstance(raw_mods, str):
        raw_mods = re.split(r"[,\s;]+", raw_mods)
    for m in raw_mods:
        mm = _MODIFIERS.get(_key(m))
        if mm and mm not in mods:
            mods.append(mm)
    necessity = _key(raw.get("necessity"))
    handling = _HANDLING.get(_key(raw.get("data_handling")))
    if handling is None:
        handling = "delete" if action == Action.remove else "retain"
    reason = re.sub(r"\s+", " ", str(raw.get("reason") or "")).strip()[:600] or "No reason given by the model."
    return AIAssessment(
        field_id=field_id,
        inferred_category=_key(raw.get("inferred_category")) or "personal",
        special_category=_bool(raw.get("special_category")),
        necessity=necessity if necessity in _NECESSITY else "unclear",  # type: ignore[arg-type]
        proposed_action=action,
        modifiers=mods,
        alternative_action=alt,
        reason=reason,
        kb_refs=_refs(raw.get("kb_refs")),
        microcopy=_opt_str(raw.get("microcopy")),
        suggested_label=_opt_str(raw.get("suggested_label")),
        retention_suggestion_days=_opt_int(raw.get("retention_suggestion_days")),
        data_handling=handling,  # type: ignore[arg-type]
        confidence=_confidence(raw.get("confidence")),
    )


async def assess_field(schema: FormSchema, field: FieldSpec, *, client: Any = None) -> AIAssessment:
    client = client or get_client()
    raw = await client.complete_json(SYSTEM_PROMPT, field_prompt(schema, field, kb_prompt_lines()))
    return normalise_assessment(field.field_id, raw)


async def assess_form(
    schema: FormSchema,
    *,
    client: Any = None,
    on_field: Optional[OnField] = None,
) -> tuple[dict[str, Optional[AIAssessment]], dict[str, str]]:
    client = client or get_client()
    results: dict[str, Optional[AIAssessment]] = {}
    errors: dict[str, str] = {}

    def notify(fid: str, a: Optional[AIAssessment], err: Optional[str]) -> None:
        if on_field is None:
            return
        try:
            on_field(fid, a, err)
        except Exception:  # noqa: BLE001 - a UI callback must never break the analysis
            pass

    if not getattr(client, "configured", True):
        msg = "AI not configured (set APERTUS_API_KEY in backend/.env)"
        for f in schema.fields:
            results[f.field_id], errors[f.field_id] = None, msg
            notify(f.field_id, None, msg)
        return results, errors

    async def one(f: FieldSpec) -> None:
        err: Optional[str] = None
        try:
            results[f.field_id] = await assess_field(schema, f, client=client)
        except Exception as exc:  # noqa: BLE001 - isolate per field
            results[f.field_id] = None
            err = f"{type(exc).__name__}: {str(exc)[:200]}"
            errors[f.field_id] = err
        notify(f.field_id, results[f.field_id], err)

    await asyncio.gather(*(one(f) for f in schema.fields))
    return results, errors
