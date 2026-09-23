# Minima — Architecture (team source of truth)

Track 1 of the Legal Hackathon (23 Sep 2026). The tool reviews a form / flow / schema definition and
classifies every field as **keep / make optional / remove / better explain**, with plain-language reasons
and legal references, without penalising inclusive optional fields.

**Differentiator:** the AI writes rules, a deterministic engine applies them, and the AI **never sees data
values** — only field metadata (names, labels, types, purposes, context). A human reviews before anything
is applied.

## 1. Decisions

| # | Decision |
|---|---|
| D1 | Engine scope: **schema first, records second**. Today we transform the form definition. A record module comes later; the rule model already carries `data_handling` for it. |
| D2 | LLM: **Apertus v1.5 70B via Swisscom** (see `docs/APERTUS.md`). OpenAI-compatible client, provider switch = 3 env vars. |
| D3 | **No AI in onboarding.** Context gathering is a plain form. No ask-back questions. Missing purpose ⇒ stricter rule + note in the report. |
| D4 | Input: structured upload (CSV/XLSX in the challenge column format, or the field grid) + AI text extraction from pasted text (stretch, always confirmed in the grid). |
| D5 | The AI reads metadata only. Never values. No value scanning. |
| D6 | **Curated legal knowledge base** (GDPR + revFADP). The AI may only cite KB ids; unknown ids are dropped. |
| D7 | **Compliance checks** (deterministic legal invariants) ‖ **AI assessment** (necessity / proportionality judgement) run independently and are **merged**: the proposal is never milder than the check floor; a milder AI suggestion is shown as an alternative the human can accept. |
| D8 | FastAPI backend + React (Vite, TS) frontend, JSON contracts, in-memory store, single process. |
| D9 | One build day. Out of scope: record module, retention expiry on data, chatbot, PDF library, auth, persistence, screenshot input. |
| D10 | Latency: per-field AI calls in parallel, checks shown instantly, per-call timeout with fallback to the rule result, demo forms **precomputed and cached** with a visible "cached · re-run live" label. |

Naming: **compliance checks** run before review. The **minimisation engine** applies the final rules after review.
Do not call both "the engine".

## 2. Pipeline

```
Input ──► Context form ──► Analysis ───────────────► Human review ──► Minimisation engine ──► Outputs
(demo /   (no AI; edits     checks (instant)   ─┐    (override,        (deterministic:         (minimised form,
 upload /  FormSchema)      AI per field     ───┴► merge → RuleSet     warnings, accept alt)   apply RuleSet)   before/after, report)
 paste*)
* paste → AI extraction → grid confirm (stretch)
```

## 3. Repo layout

```
docs/ARCHITECTURE.md   this file            docs/APERTUS.md   model access
data/                  given, unchanged
backend/app/models.py  ALL contracts — change only with a message to the whole team
backend/app/loaders/   workbook / CSV → FormSchema
backend/app/kb/        legal_kb.json (knowledge base), categories.py (category groups)
backend/app/checks/    compliance checks C01..C10
backend/app/ai/        client (Apertus), prompts, assess (parallel per field), extract (stretch)
backend/app/merge.py   checks + AI → FieldRule / RuleSet
backend/app/engine/    apply.py (schema), records.py (stub for later)
backend/app/report/    Report model + json / csv / html rendering
backend/app/cache/     precomputed RuleSets for demo forms
backend/fixtures/      F001 schema / checks / ruleset / result — frontend dev data until the API is live
backend/tests/         pytest
backend/scripts/       benchmark_apertus.py, precompute_demo.py, eval.py
frontend/src/types.ts  hand-mirrored contracts    frontend/src/api.ts  typed client
frontend/src/pages/    Start, Context, Review, Result, About
```

## 4. Contracts (`backend/app/models.py` ↔ `frontend/src/types.ts`)

Action vocabulary and strictness order used everywhere:

`keep (0) < better_explain (1) < make_optional (2) < remove (3)`

Modifiers: `delay` (collect at a later stage), `role_based` (only for specific roles), `conditional_on_purpose`
(acceptable only if a purpose gets documented). The jury's compound labels map onto `action` + `alternative_action`
+ modifiers, e.g. `remove_or_delay` = remove + delay, `keep_optional` = keep on an optional field.

| Model | Purpose |
|---|---|
| `FieldSpec` | one field of the input form: name, label, type, required, data_category, sensitive, purpose_text, retention_days, destination, third_party_shared, options, inclusivity_note |
| `FormSchema` | the form: context, audience, jurisdiction, legal_basis, stage (entry/later), source, fields |
| `CheckResult` | per field: triggered rules, `floor_action`, `protected_inclusive` |
| `AIAssessment` | per field, model output: inferred_category, necessity, proposed_action, modifiers, alternative_action, reason, kb_refs, microcopy, suggested_label, retention_suggestion_days, data_handling, confidence |
| `FieldRule` | merged, reviewable: action (current), proposed_action (merge result before any human decision), modifiers, alternative, source, check, ai, disagreement, ai_milder_suggestion, warning, reason, kb_refs, microcopy, suggested_label, retention_days, data_handling, human_override |
| `RuleSet` | all FieldRules of a form + status, progress, ai_model, cached, computed_at |
| `MinimisedForm` | output of the engine: kept fields (+microcopy), removed, delayed, diff |
| `Report` | summary, rows, no_longer_collected, retention_table, principles |
| `KBEntry` | id, law, article, title, plain_summary, tags |

## 5. Compliance checks (`checks/rules.py`)

Category groups (`kb/categories.py`): SPECIAL (health, special_category, biometric, genetic, religion, ethnicity,
sexual, political, union) · CRIMINAL (criminal_offence) · ADJACENT (`*_adjacent`: gender, legal sex, migration
status, biometric_adjacent) · IDENTITY_DOC (identity) · FINANCIAL · BEHAVIOURAL (behavioral, oauth) · PERSONAL ·
LOW (preferences, business). Unknown label → PERSONAL with an info note.

| id | condition | floor | extras |
|---|---|---|---|
| C01 | not required AND not sensitive | keep, `protected_inclusive` | never penalised |
| C02 | SPECIAL or CRIMINAL AND no purpose | remove | + delay if stage = entry; alt better_explain |
| C03 | SPECIAL or CRIMINAL AND purpose stated | keep (info) | "ensure explicit legal basis and explanation" |
| C04 | required AND no purpose | make_optional | |
| C05 | optional AND sensitive AND no purpose | better_explain | |
| C06 | third_party_shared AND no purpose | better_explain (warn) | |
| C07 | IDENTITY_DOC AND type file AND no purpose | remove, alt better_explain | warn: high-risk document |
| C08 | retention > 3650 d, or sensitive AND > 1825 d | no floor change (warn) | verify against legal retention duty |
| C09 | BEHAVIOURAL / oauth AND no purpose | remove + delay | premature access, consent bundling |
| C10 | ADJACENT AND required AND no purpose | make_optional, alt remove | offer inclusive options |

`floor_action` = strictest triggered floor. Against the 29 dataset rows the floor is equal to or milder than the
jury action everywhere except F003 `dietary_preferences` — that one is the showcase for AI + human judgement.

## 6. AI assessment (`ai/`)

One call per field, run in parallel under a semaphore and a rate limiter (see `docs/APERTUS.md`); a 429 backs off
and retries rather than failing the field. The system prompt carries an explicit **decision ladder** (stop at the
first matching line) because principles alone left the model escalating whenever a purpose was merely brief: a
plausible stated purpose is enough, an optional non-sensitive field is fine as it is, and a missing purpose means
`remove` only for special-category / criminal / identity-document / account-access data — otherwise `make_optional`.
Each call sees:
form context, a compact list of **all sibling fields** (so redundancy is visible), the target field, the KB as
`id – title – summary` lines, the action/modifier vocabulary and the JSON output schema. It does **not** see the
check results (independence). Output is parsed tolerantly (first `{` … last `}`), validated with pydantic, retried
once with the validation error, and set to `null` on the second failure ("AI unavailable, rule result stands").

## 7. Merge (`merge.py`)

1. AI missing → action = floor, source = checks.
2. AI action ≥ floor → action = AI action, modifiers = the AI's (check modifiers only when the AI matched the floor and gave none), source = both.
3. AI action < floor → action = floor, `ai_milder_suggestion` = {AI action, reason}, `disagreement = true`.
4. alternative = AI alternative or check alternative; reason = AI reason else check message; kb_refs = union.
5. Human override below the floor → `warning`, note required, shown in the report as a flagged owner decision.

## 8. API (`app/main.py`)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/demo-forms` | demo forms from the workbook |
| POST | `/api/forms` | `{source: demo, form_id}` / multipart csv,xlsx / `{source: paste, text}` → FormSchema |
| GET / PUT | `/api/forms/{id}` | read / update FormSchema (context form) |
| GET | `/api/forms/{id}/checks` | CheckResult[] (instant) |
| POST | `/api/forms/{id}/analyze?live=false` | start analysis; cached RuleSet returned immediately for demo forms |
| GET | `/api/forms/{id}/analysis` | RuleSet, partial while running |
| PUT | `/api/forms/{id}/rules` | overrides / accept alternative / set or clear a deletion deadline (`retention_days`, `clear_retention`) → RuleSet with warnings |
| POST | `/api/forms/{id}/apply` | MinimisedForm + Report |
| GET | `/api/forms/{id}/report?format=json\|csv\|html` | report |
| GET | `/api/kb` · `/api/health` | knowledge base · status |

## 9. Frontend screens

**Start** — hero, sample forms behind one small dropdown, a drop zone for CSV/XLSX as the page's main act, and a
three-step "how it works" strip. The paste-a-field-list box was dropped from the UI; `POST /api/forms
{source: paste}` still exists on the server.

**Context** — a wizard, not a form dump: one question at a time, each answered question collapsing to a line you
can reopen. What is it for (a short single-line input — it wants a few words, not an essay) → who fills it in (+ under-16s) → which law → legal basis → stage → who else sees the
answers → default retention. No field table: purposes come from the upload, and a missing one is handled by the
checks. The three new answers (`recipients`, `involves_minors`, `retention_default_days`) go into the AI prompt.

**Review** — fields grouped by their current recommendation, "Needs your decision" first (disagreement, a blocking
check, or an AI suggestion below the floor). One colour per recommendation (green keep, blue explain, amber optional,
red remove, orange decide) carries the whole page: a distribution bar and legend at the top, a rail and tinted head
per group, a rail per row. Each row also carries its own expiry control, because a deletion deadline is a decision
and not a detail. Each group collapses; each row opens a right-hand drawer holding the whole decision: why →
*what it costs you to ignore this* (consequence + benefit, with fine tiers) → the four decisions as explicit options
with the recommended one marked → **how long do you keep it** (keep indefinitely vs delete automatically, as the same
kind of explicit pair, so retention is answered on purpose instead of inherited from the spreadsheet; on a `remove`
field it says why there is nothing to keep) → legal references, each one a link to the article text
(`lib/lawLinks.ts`; `lib/consequences.ts` carries the consequence copy, keyed by check rule id). The drawer does not
dim the page: above 1100px the content shifts to make room for it.

**Report** (`report/build.py`) — leads with **Actions for the data protection representative**: the hand-over
checklist, grouped into change the form / set up deletion / sign off in writing, with the rows behind it marked by
the same action colours. Every legal reference in the report links to the article (`kb_url` / `kb_cite` in `app/kb`).

**Result** — the export page. The three export formats lead (the full report as the primary card), then stats,
"stop collecting", and "has to be deleted by" per field. No before/after preview.

**About** — principles, what the AI does and does not see, the knowledge base.

Build against `backend/fixtures/*.json` first, then switch `api.ts` to the server.

## 10. Team rules

- `models.py` and `types.ts` change only with a message to everyone.
- Fixtures are the shared truth until the API is live.
- Every module has a pure-function entry point that runs from a test without the server.
- Workstreams: W1 backend core · W2 AI (benchmark → client → prompts → assess → precompute → eval loop) ·
  W3 frontend · W4 legal content (KB wording, check messages, microcopy tone, About text).

## 11. Verification

`pytest backend/tests` · `python backend/scripts/benchmark_apertus.py` · `python backend/scripts/eval.py --live|--cached|--checks-only`
(targets: lenient ≥ 25/29, flag ≥ 27/29) · manual end-to-end on F001 and F003 · Docker build and run.
