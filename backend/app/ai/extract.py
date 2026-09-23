"""Paste-to-schema: one Apertus call turns a pasted field list / HTML / notes into a FormSchema (source="paste").
The result is always shown in the grid for the user to confirm before any analysis (decision D4).
"""

from __future__ import annotations

import re
from typing import Any, Optional

from app.ai.client import AIError, get_client
from app.ai.prompts import EXTRACT_SYSTEM, extract_prompt
from app.loaders.xlsx import derive_stage
from app.models import FieldSpec, FormSchema

_TYPES = {"text", "textarea", "email", "number", "date", "dropdown", "file", "oauth", "checkbox", "other"}
_TYPE_HINTS = [
    ("email", "email"), ("e-mail", "email"), ("upload", "file"), ("scan", "file"), ("attach", "file"),
    ("date", "date"), ("birth", "date"), ("calendar", "oauth"), ("connect", "oauth"),
    ("select", "dropdown"), ("choose", "dropdown"), ("comment", "textarea"), ("describe", "textarea"),
    ("history", "textarea"), ("amount", "number"), ("income", "number"), ("size", "dropdown"),
]


def slugify(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")
    return s or "field"


def _type(raw: Any, label: str) -> str:
    t = str(raw or "").strip().lower()
    if t in _TYPES:
        return t
    low = label.lower()
    for hint, typ in _TYPE_HINTS:
        if hint in low:
            return typ
    return "text"


def _required(raw: Any, label: str) -> bool:
    if isinstance(raw, bool):
        return raw
    low = f"{raw or ''} {label}".lower()
    return "*" in label or "required" in low or "mandatory" in low or str(raw).strip().lower() in ("true", "yes", "y")


async def extract_fields(
    text: str,
    *,
    name: Optional[str] = None,
    business_context: Optional[str] = None,
    client: Any = None,
) -> FormSchema:
    client = client or get_client()
    if not getattr(client, "configured", True):
        raise AIError("AI text extraction needs Apertus: set APERTUS_API_KEY in backend/.env")
    raw = await client.complete_json(EXTRACT_SYSTEM, extract_prompt(text, name, business_context))

    fields: list[FieldSpec] = []
    seen: set[str] = set()
    for i, f in enumerate(raw.get("fields") or [], start=1):
        if not isinstance(f, dict):
            continue
        label = str(f.get("label") or f.get("name") or f"Field {i}").strip()
        fid = slugify(str(f.get("name") or label))
        while fid in seen:
            fid = f"{fid}_{i}"
        seen.add(fid)
        opts = f.get("options")
        purpose = f.get("purpose_text")
        fields.append(FieldSpec(
            field_id=fid, order=i, name=fid,
            label=label.rstrip("* ").strip() or label,
            type=_type(f.get("type"), label),  # type: ignore[arg-type]
            required=_required(f.get("required"), label),
            data_category=(str(f.get("data_category")).strip().lower() or None) if f.get("data_category") else None,
            purpose_text=str(purpose).strip() if purpose and str(purpose).strip().lower() not in ("null", "none") else None,
            options=[str(o) for o in opts] if isinstance(opts, list) and opts else None,
        ))
    if not fields:
        raise AIError("No fields could be extracted from the pasted text.")

    form_name = name or str(raw.get("name") or "Pasted form").strip()
    ctx = business_context or str(raw.get("business_context") or "").strip()
    return FormSchema(
        form_id="paste", name=form_name, business_context=ctx,
        stage=derive_stage(form_name, ctx), source="paste", fields=fields,  # type: ignore[arg-type]
    )
