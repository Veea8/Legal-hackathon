"""Prompt templates. The AI sees field metadata only (names, labels, types, purposes, context), never values.

field_prompt() shows ALL sibling fields (so redundancy is visible), the target field in full, the legal
knowledge base, the vocabularies and the exact JSON shape of `AIAssessment`. The compliance-check results are
deliberately NOT included: checks and AI run independently (decision D7).
"""

from __future__ import annotations

from typing import Optional

from app.models import FieldSpec, FormSchema

SYSTEM_PROMPT = """You are a privacy-by-design reviewer helping product, legal and operations teams apply data minimisation under the EU GDPR and the Swiss revFADP (nDSG).
You only ever see field METADATA: names, labels, types, stated purposes and business context. You never see data values.

Principles:
- Data minimisation and purpose limitation: a field is justified only by a documented purpose it is necessary for. "Mandatory" is not the default; a required field needs a reason, otherwise make it optional.
- Stage appropriateness: entry-stage forms (signup, lead capture, application, onboarding) should not collect special-category or high-risk data. Collect it later, or only for the roles/cases that need it.
- Special categories (health, religion, ethnicity, political opinion, sexual life, biometric/genetic data, criminal-offence data; under Swiss law also social-assistance measures) need an explicit legal basis and a clearly explained purpose.
- Do NOT penalise optional inclusive fields (preferred name, pronouns, language, accessibility needs, shirt size). If optional and low-risk, keep them.
- Redundancy: if a sibling field already serves the purpose, the extra field is unnecessary.
- Retention and third-party sharing must be proportionate and explained to the person.
- Sensitive data with a clear, necessary purpose (e.g. bank account for salary, insurance number for billing) is fine: keep it, explain it.

Actions (strictness keep < better_explain < make_optional < remove): keep | better_explain | make_optional | remove.
Modifiers: delay (collect at a later stage) | role_based (only for specific roles/cases) | conditional_on_purpose (acceptable only once a purpose is documented).
Cite ONLY knowledge-base ids from the list you are given.
Reply with a single JSON object and nothing else: no prose, no code fences."""


def _yn(v: Optional[bool]) -> str:
    return "yes" if v else "no"


def _sibling_line(f: FieldSpec, target: bool) -> str:
    purpose = f.purpose_text.strip() if f.has_purpose else "NO PURPOSE STATED"
    extras = []
    if f.retention_days is not None:
        extras.append(f"retention {f.retention_days}d")
    if f.destination:
        extras.append(f"-> {f.destination}")
    if f.third_party_shared:
        extras.append("shared with third party")
    tail = f" ({', '.join(extras)})" if extras else ""
    mark = "=> " if target else "- "
    return f"{mark}{f.name}{'*' if f.required else ''} [{f.type}] {f.data_category or 'category?'}: {purpose}{tail}"


def field_prompt(schema: FormSchema, field: FieldSpec, kb_lines: str) -> str:
    stage = "entry stage (first contact: signup / lead / application / onboarding)" if schema.stage == "entry" else "later stage"
    siblings = "\n".join(_sibling_line(f, f.field_id == field.field_id) for f in schema.fields)
    return f"""FORM: {schema.name} — {schema.business_context or 'no context given'}
Audience: {schema.audience or 'not stated'} · Jurisdiction: {schema.jurisdiction} · Legal basis: {schema.legal_basis or 'not stated'} · Stage: {stage}

ALL FIELDS IN THIS FORM (* = required; => marks the field to assess):
{siblings}

FIELD TO ASSESS: {field.name}
- label: {field.label}
- type: {field.type}
- required: {_yn(field.required)}
- category as labelled by the form owner: {field.data_category or 'not given'}; sensitive flag: {_yn(field.sensitive)}
- purpose: {field.purpose_text.strip() if field.has_purpose else 'NO PURPOSE STATED'}
- retention: {f'{field.retention_days} days' if field.retention_days is not None else 'not given'}; destination: {field.destination or 'not given'}; shared with third parties: {_yn(field.third_party_shared)}
- inclusivity note from the owner: {field.inclusivity_note or 'none'}

KNOWLEDGE BASE (cite by id only):
{kb_lines}

Respond with exactly this JSON shape:
{{
  "inferred_category": "personal | contact | health | special_category | criminal | identity_document | financial | behavioural | preferences | business | other",
  "special_category": true or false,
  "necessity": "necessary | useful | unnecessary | unclear",
  "proposed_action": "keep | better_explain | make_optional | remove",
  "modifiers": ["delay", "role_based", "conditional_on_purpose"] or [],
  "alternative_action": "keep | better_explain | make_optional | remove" or null,
  "reason": "max 60 words, plain language for a product owner",
  "kb_refs": ["knowledge-base ids"],
  "microcopy": "one sentence telling the person why this is asked and what happens with it, or null if the field should be removed",
  "suggested_label": "a clearer label, or null",
  "retention_suggestion_days": integer or null,
  "data_handling": "retain | delete | pseudonymise | expire",
  "confidence": number between 0 and 1
}}"""


EXTRACT_SYSTEM = """You convert a pasted description of a form (a field list, HTML, or notes) into structured field metadata.
Reply with a single JSON object and nothing else."""


def extract_prompt(text: str, name: Optional[str] = None, business_context: Optional[str] = None) -> str:
    return f"""Form name: {name or 'unknown (infer a short one)'}
Business context: {business_context or 'unknown (infer one sentence if possible)'}

PASTED FORM:
\"\"\"
{text.strip()[:6000]}
\"\"\"

Extract every input field. Respond with exactly this JSON shape:
{{
  "name": "short form name",
  "business_context": "one sentence",
  "fields": [
    {{
      "name": "snake_case_identifier",
      "label": "label as shown to the person",
      "type": "text | textarea | email | number | date | dropdown | file | oauth | checkbox | other",
      "required": true or false,
      "data_category": "personal | contact | health | special_category | criminal | identity | financial | behavioral | preferences | business | other",
      "purpose_text": "purpose if the text states one, else null",
      "options": ["dropdown options"] or null
    }}
  ]
}}"""
