"""All data contracts of Minima.

This file is the shared contract between backend modules and the frontend
(`frontend/src/types.ts` mirrors it). Change it only with a message to the whole team.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------


class Action(str, Enum):
    keep = "keep"
    better_explain = "better_explain"
    make_optional = "make_optional"
    remove = "remove"


ACTION_STRICTNESS: dict[Action, int] = {
    Action.keep: 0,
    Action.better_explain: 1,
    Action.make_optional: 2,
    Action.remove: 3,
}


def stricter(a: Action, b: Action) -> Action:
    """Return the stricter of two actions (strictness order keep < better_explain < make_optional < remove)."""
    return a if ACTION_STRICTNESS[a] >= ACTION_STRICTNESS[b] else b


def is_milder(a: Action, b: Action) -> bool:
    return ACTION_STRICTNESS[a] < ACTION_STRICTNESS[b]


class Modifier(str, Enum):
    delay = "delay"  # collect at a later stage, not at entry
    role_based = "role_based"  # collect only for specific roles / cases
    conditional_on_purpose = "conditional_on_purpose"  # acceptable only once a purpose is documented


FieldType = Literal[
    "text", "textarea", "email", "number", "date", "dropdown", "file", "oauth", "checkbox", "other"
]
Jurisdiction = Literal["eu", "ch", "both"]
LegalBasis = Literal["consent", "contract", "legal_obligation", "legitimate_interest"]
Stage = Literal["entry", "later"]
Source = Literal["demo", "upload", "paste"]
Severity = Literal["info", "warn", "block"]
Necessity = Literal["necessary", "useful", "unnecessary", "unclear"]
DataHandling = Literal["retain", "delete", "pseudonymise", "expire"]
RuleSource = Literal["checks", "ai", "both", "human"]
RuleSetStatus = Literal["running", "proposed", "reviewed", "applied"]


# ---------------------------------------------------------------------------
# Input: the form definition (what the AI is allowed to see)
# ---------------------------------------------------------------------------


class FieldSpec(BaseModel):
    field_id: str
    order: int = 0
    name: str
    label: str
    type: FieldType = "text"
    required: bool = False
    data_category: Optional[str] = None
    sensitive: Optional[bool] = None
    purpose_text: Optional[str] = None  # empty / None = no purpose stated
    retention_days: Optional[int] = None
    destination: Optional[str] = None  # CRM, HRIS, Billing, Files, Integrations, Ops, CaseMgmt, ...
    third_party_shared: Optional[bool] = None
    options: Optional[list[str]] = None
    inclusivity_note: Optional[str] = None

    @property
    def has_purpose(self) -> bool:
        return bool(self.purpose_text and self.purpose_text.strip())


class FormSchema(BaseModel):
    form_id: str
    name: str
    business_context: str = ""
    audience: Optional[str] = None  # who fills the form in (patients, leads, employees, ...)
    jurisdiction: Jurisdiction = "both"
    legal_basis: Optional[LegalBasis] = None
    stage: Stage = "entry"
    source: Source = "demo"
    # Answered in the context wizard; all optional so older payloads keep working.
    recipients: Optional[str] = None  # who else sees the data (processors, third parties)
    involves_minors: Optional[bool] = None  # audience includes people under 16
    retention_default_days: Optional[int] = None  # house rule for "how long may we keep it"
    fields: list[FieldSpec] = Field(default_factory=list)

    def field(self, field_id: str) -> Optional[FieldSpec]:
        return next((f for f in self.fields if f.field_id == field_id), None)


# ---------------------------------------------------------------------------
# Analysis: compliance checks and AI assessment (independent of each other)
# ---------------------------------------------------------------------------


class TriggeredRule(BaseModel):
    rule_id: str
    severity: Severity
    floor_action: Action
    alternative_action: Optional[Action] = None
    modifiers: list[Modifier] = Field(default_factory=list)
    kb_refs: list[str] = Field(default_factory=list)
    message: str


class CheckResult(BaseModel):
    field_id: str
    triggered: list[TriggeredRule] = Field(default_factory=list)
    floor_action: Action = Action.keep
    protected_inclusive: bool = False


class AIAssessment(BaseModel):
    field_id: str
    inferred_category: str = "personal"
    special_category: bool = False
    necessity: Necessity = "unclear"
    proposed_action: Action
    modifiers: list[Modifier] = Field(default_factory=list)
    alternative_action: Optional[Action] = None
    reason: str
    kb_refs: list[str] = Field(default_factory=list)
    microcopy: Optional[str] = None  # "why we ask" text shown under the field
    suggested_label: Optional[str] = None
    retention_suggestion_days: Optional[int] = None
    data_handling: DataHandling = "retain"
    confidence: float = Field(0.5, ge=0.0, le=1.0)


# ---------------------------------------------------------------------------
# Merged, reviewable rules
# ---------------------------------------------------------------------------


class MilderSuggestion(BaseModel):
    action: Action
    justification: str


class HumanOverride(BaseModel):
    action: Action
    note: str = ""


class FieldRule(BaseModel):
    field_id: str
    action: Action  # current action (after any human decision)
    proposed_action: Action  # merge result before any human decision
    modifiers: list[Modifier] = Field(default_factory=list)
    alternative_action: Optional[Action] = None
    source: RuleSource = "checks"
    check: CheckResult
    ai: Optional[AIAssessment] = None
    disagreement: bool = False
    ai_milder_suggestion: Optional[MilderSuggestion] = None
    warning: Optional[str] = None
    reason: str = ""
    kb_refs: list[str] = Field(default_factory=list)
    microcopy: Optional[str] = None
    suggested_label: Optional[str] = None
    retention_days: Optional[int] = None
    data_handling: DataHandling = "retain"
    human_override: Optional[HumanOverride] = None


class RuleSet(BaseModel):
    form_id: str
    status: RuleSetStatus = "running"
    rules: list[FieldRule] = Field(default_factory=list)
    fields_done: int = 0
    fields_total: int = 0
    ai_model: Optional[str] = None
    cached: bool = False
    computed_at: Optional[datetime] = None
    ai_errors: dict[str, str] = Field(default_factory=dict)  # field_id -> short error text

    def rule(self, field_id: str) -> Optional[FieldRule]:
        return next((r for r in self.rules if r.field_id == field_id), None)


# ---------------------------------------------------------------------------
# Engine output
# ---------------------------------------------------------------------------


class MinimisedField(FieldSpec):
    microcopy: Optional[str] = None
    action: Action = Action.keep
    modifiers: list[Modifier] = Field(default_factory=list)


class RemovedField(BaseModel):
    field_id: str
    label: str
    reason: str


class DelayedField(BaseModel):
    field_id: str
    label: str
    note: str


class Diff(BaseModel):
    removed: list[str] = Field(default_factory=list)
    delayed: list[str] = Field(default_factory=list)
    made_optional: list[str] = Field(default_factory=list)
    explained: list[str] = Field(default_factory=list)
    unchanged: list[str] = Field(default_factory=list)


class MinimisedForm(BaseModel):
    form_id: str
    name: str
    fields: list[MinimisedField] = Field(default_factory=list)
    removed: list[RemovedField] = Field(default_factory=list)
    delayed: list[DelayedField] = Field(default_factory=list)
    diff: Diff = Field(default_factory=Diff)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


class ReportFormInfo(BaseModel):
    form_id: str
    name: str
    business_context: str
    jurisdiction: Jurisdiction


class ReportSummary(BaseModel):
    n_fields: int
    counts: dict[str, int]  # action -> count
    n_special_category: int
    n_overrides_flagged: int
    n_ai_unavailable: int = 0


class ReportRow(BaseModel):
    field_id: str
    label: str
    original_required: bool
    original_category: Optional[str]
    action: Action
    modifiers: list[Modifier] = Field(default_factory=list)
    reason: str
    kb_refs: list[str] = Field(default_factory=list)
    kb_titles: list[str] = Field(default_factory=list)
    source: RuleSource
    owner_decision: str  # "accepted proposal" | "override: keep (note)" | "accepted AI suggestion" ...
    warning: Optional[str] = None
    retention_days: Optional[int] = None
    delete_by: Optional[str] = None  # ISO date: field must be deleted by then
    data_handling: DataHandling = "retain"


class RetentionRow(BaseModel):
    field_id: str
    label: str
    current_days: Optional[int]
    suggested_days: Optional[int]


class Report(BaseModel):
    form: ReportFormInfo
    summary: ReportSummary
    rows: list[ReportRow]
    no_longer_collected: list[str]  # labels of removed / delayed fields, for the data-collection owner
    retention_table: list[RetentionRow]
    principles: list[str]  # kb ids applied anywhere
    ai_model: Optional[str] = None
    cached: bool = False
    generated_at: datetime


# ---------------------------------------------------------------------------
# Knowledge base
# ---------------------------------------------------------------------------


class KBEntry(BaseModel):
    id: str
    law: Literal["gdpr", "fadp"]
    article: str
    title: str
    plain_summary: str
    tags: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# API request / response helpers
# ---------------------------------------------------------------------------


class DemoFormInfo(BaseModel):
    form_id: str
    name: str
    business_context: str
    n_fields: int
    cached: bool = False


class CreateFormRequest(BaseModel):
    source: Literal["demo", "paste", "schema"]
    form_id: Optional[str] = None  # for source = demo
    text: Optional[str] = None  # for source = paste
    # source = schema: a complete FormSchema, no AI involved. Used by callers that already hold
    # structured fields, and to rebuild a session the server has forgotten (restart, redeploy).
    schema_: Optional["FormSchema"] = Field(None, alias="schema")
    demo_form_id: Optional[str] = None  # keeps the precomputed cache reachable after a rebuild
    name: Optional[str] = None
    business_context: Optional[str] = None

    model_config = {"populate_by_name": True}


class RuleOverride(BaseModel):
    field_id: str
    action: Optional[Action] = None  # explicit override
    accept_alternative: bool = False  # take alternative_action
    accept_ai_suggestion: bool = False  # take ai_milder_suggestion
    retention_days: Optional[int] = Field(None, ge=1, le=36500)  # set a deletion deadline
    clear_retention: bool = False  # drop the deadline again
    note: str = ""


class OverridesRequest(BaseModel):
    overrides: list[RuleOverride]


class ApplyResponse(BaseModel):
    minimised: MinimisedForm
    report: Report


class HealthResponse(BaseModel):
    ok: bool
    model: Optional[str]
    base_url_set: bool
    api_key_set: bool
    cached_forms: list[str]
    json_mode: Optional[bool] = None


# ---------------------------------------------------------------------------
# Integrations — the report, sent where the work happens
# ---------------------------------------------------------------------------


Destination = Literal["teams", "slack", "webhook", "email", "jira", "calendar"]


class DeliveryRequest(BaseModel):
    destination: Destination
    url: str = ""  # teams | slack | webhook
    to: str = ""  # email
    project_key: str = "DPO"  # jira


class DeliveryPreview(BaseModel):
    """Exactly what would go out. The send path builds the same body from the same function."""

    destination: Destination
    title: str
    subtitle: str
    body_format: Literal["json", "text", "ics"]
    body: str
    summary: str  # "9 actions · 6 deletion deadlines · 1 flagged decision"
    n_tasks: int
    sendable: bool  # False for email / jira / calendar — those hand you the payload instead
    needs_url: bool
    url_label: Optional[str] = None
    url_placeholder: Optional[str] = None
    note: Optional[str] = None  # what happens when you press the button
    link: Optional[str] = None  # mailto: or a download href


class DeliveryRecord(BaseModel):
    """One outbound HTTP delivery that actually left the machine. The target is stored redacted."""

    id: str
    destination: Destination
    target: str
    at: datetime
    ok: bool
    status: Optional[int] = None
    detail: str = ""
    summary: str


class SendResponse(BaseModel):
    record: DeliveryRecord
    log: list[DeliveryRecord]
