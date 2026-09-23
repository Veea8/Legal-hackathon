// Hand-mirrored from backend/app/models.py. Change only together with that file.

export type Action = "keep" | "better_explain" | "make_optional" | "remove";
export type Modifier = "delay" | "role_based" | "conditional_on_purpose";
export type FieldType =
  | "text" | "textarea" | "email" | "number" | "date" | "dropdown" | "file" | "oauth" | "checkbox" | "other";
export type Jurisdiction = "eu" | "ch" | "both";
export type LegalBasis = "consent" | "contract" | "legal_obligation" | "legitimate_interest";
export type Stage = "entry" | "later";
export type Source = "demo" | "upload" | "paste";
export type Severity = "info" | "warn" | "block";
export type Necessity = "necessary" | "useful" | "unnecessary" | "unclear";
export type DataHandling = "retain" | "delete" | "pseudonymise" | "expire";
export type RuleSource = "checks" | "ai" | "both" | "human";
export type RuleSetStatus = "running" | "proposed" | "reviewed" | "applied";

export interface FieldSpec {
  field_id: string;
  order: number;
  name: string;
  label: string;
  type: FieldType;
  required: boolean;
  data_category: string | null;
  sensitive: boolean | null;
  purpose_text: string | null;
  retention_days: number | null;
  destination: string | null;
  third_party_shared: boolean | null;
  options: string[] | null;
  inclusivity_note: string | null;
}

export interface FormSchema {
  form_id: string;
  name: string;
  business_context: string;
  audience: string | null;
  jurisdiction: Jurisdiction;
  legal_basis: LegalBasis | null;
  stage: Stage;
  source: Source;
  recipients: string | null;
  involves_minors: boolean | null;
  retention_default_days: number | null;
  fields: FieldSpec[];
}

export interface TriggeredRule {
  rule_id: string;
  severity: Severity;
  floor_action: Action;
  alternative_action: Action | null;
  modifiers: Modifier[];
  kb_refs: string[];
  message: string;
}

export interface CheckResult {
  field_id: string;
  triggered: TriggeredRule[];
  floor_action: Action;
  protected_inclusive: boolean;
}

export interface AIAssessment {
  field_id: string;
  inferred_category: string;
  special_category: boolean;
  necessity: Necessity;
  proposed_action: Action;
  modifiers: Modifier[];
  alternative_action: Action | null;
  reason: string;
  kb_refs: string[];
  microcopy: string | null;
  suggested_label: string | null;
  retention_suggestion_days: number | null;
  data_handling: DataHandling;
  confidence: number;
}

export interface MilderSuggestion {
  action: Action;
  justification: string;
}

export interface HumanOverride {
  action: Action;
  note: string;
}

export interface FieldRule {
  field_id: string;
  action: Action;
  proposed_action: Action;
  modifiers: Modifier[];
  alternative_action: Action | null;
  source: RuleSource;
  check: CheckResult;
  ai: AIAssessment | null;
  disagreement: boolean;
  ai_milder_suggestion: MilderSuggestion | null;
  warning: string | null;
  reason: string;
  kb_refs: string[];
  microcopy: string | null;
  suggested_label: string | null;
  retention_days: number | null;
  data_handling: DataHandling;
  human_override: HumanOverride | null;
}

export interface RuleSet {
  form_id: string;
  status: RuleSetStatus;
  rules: FieldRule[];
  fields_done: number;
  fields_total: number;
  ai_model: string | null;
  cached: boolean;
  computed_at: string | null;
  ai_errors: Record<string, string>;
}

export interface MinimisedField extends FieldSpec {
  microcopy: string | null;
  action: Action;
  modifiers: Modifier[];
}

export interface RemovedField {
  field_id: string;
  label: string;
  reason: string;
}

export interface DelayedField {
  field_id: string;
  label: string;
  note: string;
}

export interface Diff {
  removed: string[];
  delayed: string[];
  made_optional: string[];
  explained: string[];
  unchanged: string[];
}

export interface MinimisedForm {
  form_id: string;
  name: string;
  fields: MinimisedField[];
  removed: RemovedField[];
  delayed: DelayedField[];
  diff: Diff;
}

export interface ReportFormInfo {
  form_id: string;
  name: string;
  business_context: string;
  jurisdiction: Jurisdiction;
}

export interface ReportSummary {
  n_fields: number;
  counts: Record<string, number>;
  n_special_category: number;
  n_overrides_flagged: number;
  n_ai_unavailable: number;
}

export interface ReportRow {
  field_id: string;
  label: string;
  original_required: boolean;
  original_category: string | null;
  action: Action;
  modifiers: Modifier[];
  reason: string;
  kb_refs: string[];
  kb_titles: string[];
  source: RuleSource;
  owner_decision: string;
  warning: string | null;
  retention_days: number | null;
  delete_by: string | null;
  data_handling: DataHandling;
}

export interface RetentionRow {
  field_id: string;
  label: string;
  current_days: number | null;
  suggested_days: number | null;
}

export interface Report {
  form: ReportFormInfo;
  summary: ReportSummary;
  rows: ReportRow[];
  no_longer_collected: string[];
  retention_table: RetentionRow[];
  principles: string[];
  ai_model: string | null;
  cached: boolean;
  generated_at: string;
}

export interface KBEntry {
  id: string;
  law: "gdpr" | "fadp";
  article: string;
  title: string;
  plain_summary: string;
  tags: string[];
}

export interface DemoFormInfo {
  form_id: string;
  name: string;
  business_context: string;
  n_fields: number;
  cached: boolean;
}

export interface RuleOverride {
  field_id: string;
  action?: Action | null;
  accept_alternative?: boolean;
  accept_ai_suggestion?: boolean;
  retention_days?: number | null;
  clear_retention?: boolean;
  note?: string;
}

export interface ApplyResponse {
  minimised: MinimisedForm;
  report: Report;
}

export interface HealthResponse {
  ok: boolean;
  model: string | null;
  base_url_set: boolean;
  api_key_set: boolean;
  cached_forms: string[];
  json_mode: boolean | null;
}
