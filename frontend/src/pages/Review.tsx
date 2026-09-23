import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError, api, errorMessage } from "../api";
import ActionBadge from "../components/ActionBadge";
import DecisionDrawer from "../components/DecisionDrawer";
import { deadlineFrom } from "../lib/actions";
import { stakeLine } from "../lib/consequences";
import type { Action, CheckResult, FieldRule, FieldSpec, FormSchema, KBEntry, RuleOverride, RuleSet } from "../types";

type BucketKey = "keep" | "review" | "remove";

const BUCKETS: { key: BucketKey; title: string; sub: string }[] = [
  { key: "keep", title: "Keep", sub: "No change needed" },
  { key: "review", title: "Review", sub: "Adjust or explain" },
  { key: "remove", title: "Remove", sub: "Stop collecting" },
];

const ACTION_ORDER: Record<Action, number> = { remove: 0, make_optional: 1, better_explain: 2, keep: 3 };

function requiresSignoff(rule: FieldRule | undefined, check: CheckResult | undefined): boolean {
  if (!rule) return false;
  if (rule.disagreement || rule.ai_milder_suggestion) return true;
  return (check?.triggered ?? []).some((item) => item.severity === "block");
}

function isUnresolved(rule: FieldRule | undefined, check: CheckResult | undefined): boolean {
  return requiresSignoff(rule, check) && !rule?.human_override;
}

function actionSummary(rule: FieldRule | undefined, unresolved: boolean): string {
  if (!rule) return "Assessment in progress…";
  if (unresolved) return "Confirm this recommendation before export.";
  if (rule.action === "remove") return "This field should no longer be collected.";
  if (rule.action === "make_optional") return "Keep it, but let people skip it.";
  if (rule.action === "better_explain") return "Keep it and clearly explain why it is needed.";
  return "Necessary and proportionate—no change needed.";
}

export default function Review() {
  const { id = "" } = useParams();
  const nav = useNavigate();
  const [schema, setSchema] = useState<FormSchema | null>(null);
  const [checks, setChecks] = useState<CheckResult[]>([]);
  const [kb, setKb] = useState<KBEntry[]>([]);
  const [ruleset, setRuleset] = useState<RuleSet | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [rowErrors, setRowErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [activeBucket, setActiveBucket] = useState<BucketKey | null>("review");
  const [selected, setSelected] = useState<string | null>(null);
  const fieldButtons = useRef(new Map<string, HTMLButtonElement>());

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.getForm(id), api.checks(id), api.kb()])
      .then(([form, results, entries]) => {
        if (cancelled) return;
        setSchema(form);
        setChecks(results);
        setKb(entries);
      })
      .catch((e) => !cancelled && setError(errorMessage(e)));
    return () => { cancelled = true; };
  }, [id]);

  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;
    async function tick() {
      try {
        let next: RuleSet;
        try {
          next = await api.analysis(id);
        } catch (e) {
          if (e instanceof ApiError && e.status === 404) next = await api.analyze(id, false);
          else throw e;
        }
        if (cancelled) return;
        setRuleset(next);
        if (next.status === "running") timer = window.setTimeout(() => void tick(), 900);
      } catch (e) {
        if (!cancelled) setError(errorMessage(e));
      }
    }
    void tick();
    return () => { cancelled = true; if (timer) window.clearTimeout(timer); };
  }, [id]);

  const onOverride = useCallback(async (override: RuleOverride) => {
    setRowErrors((current) => ({ ...current, [override.field_id]: "" }));
    try {
      setRuleset(await api.putRules(id, [override]));
    } catch (e) {
      setRowErrors((current) => ({ ...current, [override.field_id]: errorMessage(e) }));
    }
  }, [id]);

  const checkById = useMemo(() => new Map(checks.map((check) => [check.field_id, check])), [checks]);
  const ruleById = useMemo(() => new Map((ruleset?.rules ?? []).map((rule) => [rule.field_id, rule])), [ruleset]);

  const bucketed = useMemo(() => {
    const output = new Map<BucketKey, FieldSpec[]>(BUCKETS.map((bucket) => [bucket.key, []]));
    const sourceOrder = new Map((schema?.fields ?? []).map((field, index) => [field.field_id, index]));
    for (const field of schema?.fields ?? []) {
      const rule = ruleById.get(field.field_id);
      const key: BucketKey = rule?.action === "remove" ? "remove" : rule?.action === "keep" ? "keep" : "review";
      output.get(key)!.push(field);
    }
    output.get("review")!.sort((a, b) => {
      const unresolved = (field: FieldSpec) => isUnresolved(ruleById.get(field.field_id), checkById.get(field.field_id)) ? 0 : 1;
      const actionA = ruleById.get(a.field_id)?.action ?? "keep";
      const actionB = ruleById.get(b.field_id)?.action ?? "keep";
      return unresolved(a) - unresolved(b) || ACTION_ORDER[actionA] - ACTION_ORDER[actionB] || sourceOrder.get(a.field_id)! - sourceOrder.get(b.field_id)!;
    });
    return output;
  }, [schema, ruleById, checkById]);

  const flatOrder = useMemo(
    () => BUCKETS.flatMap((bucket) => (bucketed.get(bucket.key) ?? []).map((field) => field.field_id)),
    [bucketed],
  );

  async function applyRules() {
    setBusy(true);
    setError(null);
    try {
      await api.apply(id);
      nav(`/forms/${id}/result`);
    } catch (e) {
      setError(errorMessage(e));
      setBusy(false);
    }
  }

  function closeField() {
    const previous = selected;
    setSelected(null);
    window.requestAnimationFrame(() => previous && fieldButtons.current.get(previous)?.focus());
  }

  if (!schema) return error ? <div className="error" role="alert">{error}</div> : <p className="muted">Loading…</p>;

  const running = !ruleset || ruleset.status === "running";
  const total = schema.fields.length;
  const signoffTotal = schema.fields.filter((field) => requiresSignoff(ruleById.get(field.field_id), checkById.get(field.field_id))).length;
  const unresolved = schema.fields.filter((field) => isUnresolved(ruleById.get(field.field_id), checkById.get(field.field_id))).length;
  const reviewed = signoffTotal - unresolved;
  const nErrors = ruleset ? Object.keys(ruleset.ai_errors).length : 0;
  const selectedField = schema.fields.find((field) => field.field_id === selected);
  const selectedRule = selectedField ? ruleById.get(selectedField.field_id) : undefined;
  const selectedCheck = selectedField ? checkById.get(selectedField.field_id) : undefined;
  const selectedIndex = selected ? flatOrder.indexOf(selected) : -1;

  return (
    <>
      <header className="review-head">
        <div>
          <p className="eyebrow review-eyebrow">Decision review</p>
          <h1>{schema.name}</h1>
          <p className="muted small">
            {total} fields · {schema.business_context} · <Link to={`/forms/${id}/context`}>change context</Link>
          </p>
        </div>
        <div className="review-submit">
          {running ? (
            <span className="tag tag-warn"><i className="tag-dot pulse" /> Assessing {ruleset ? `${ruleset.fields_done}/${ruleset.fields_total}` : ""}</span>
          ) : (
            <span className="tag tag-live">{ruleset?.cached ? "Cached assessment" : ruleset?.ai_model ?? "Checks only"}</span>
          )}
          <button type="button" onClick={() => void applyRules()} disabled={busy || running || unresolved > 0}>
            {busy ? "Applying…" : "Apply and export →"}
          </button>
          {!running && unresolved > 0 && <span className="submit-hint">Review {unresolved} field{unresolved === 1 ? "" : "s"} to continue</span>}
        </div>
      </header>

      {error && <div className="error" role="alert">{error}</div>}

      {!running && ruleset && signoffTotal > 0 && (
        <div className={`signoff-progress${unresolved === 0 ? " complete" : ""}`} role="status">
          <span aria-hidden="true">{unresolved === 0 ? "✓" : "!"}</span>
          <strong>{unresolved === 0 ? "All decisions reviewed" : `${unresolved} decision${unresolved === 1 ? "" : "s"} left`}</strong>
          <small>{reviewed} of {signoffTotal} confirmed</small>
        </div>
      )}

      {nErrors > 0 && (
        <div className="review-notice" role="status">
          <strong>AI unavailable for {nErrors} field{nErrors === 1 ? "" : "s"}.</strong>
          <span>The deterministic compliance checks still ran and remain authoritative.</span>
        </div>
      )}

      <div className={`review-workspace${selectedField ? " with-detail" : ""}`}>
        <main className="review-sections">
          <div className="decision-tabs" aria-label="Filter fields by recommendation">
            {BUCKETS.map((bucket) => {
              const count = bucketed.get(bucket.key)?.length ?? 0;
              return (
                <button
                  key={bucket.key}
                  type="button"
                  className={`decision-tab tab-${bucket.key}${activeBucket === bucket.key ? " active" : ""}`}
                  aria-expanded={activeBucket === bucket.key}
                  onClick={() => setActiveBucket((current) => current === bucket.key ? null : bucket.key)}
                >
                  <span className="tab-dot" aria-hidden="true" />
                  <span><strong>{bucket.title}</strong><small>{bucket.sub}</small></span>
                  <b>{count}</b>
                </button>
              );
            })}
          </div>

          {activeBucket && (
            <section className={`review-bucket bucket-${activeBucket}`}>
              <header className="bucket-label">
                <h2>{BUCKETS.find((bucket) => bucket.key === activeBucket)?.title}</h2>
                <span>{BUCKETS.find((bucket) => bucket.key === activeBucket)?.sub}</span>
              </header>
              <div className="field-list">
                {(bucketed.get(activeBucket) ?? []).length === 0 ? (
                  <p className="empty-bucket">No fields in this section.</p>
                ) : (
                  (bucketed.get(activeBucket) ?? []).map((field) => {
                      const rule = ruleById.get(field.field_id);
                      const check = checkById.get(field.field_id);
                      const needsSignoff = isUnresolved(rule, check);
                      const stake = stakeLine(rule, check);
                      const deadline = rule?.action !== "remove" ? deadlineFrom(rule?.retention_days) : null;
                      return (
                        <button
                          key={field.field_id}
                          ref={(element) => {
                            if (element) fieldButtons.current.set(field.field_id, element);
                            else fieldButtons.current.delete(field.field_id);
                          }}
                          type="button"
                          className={`field-row${selected === field.field_id ? " selected" : ""}${rule ? "" : " pending"}`}
                          onClick={() => setSelected(field.field_id)}
                          aria-label={`Review ${field.label}`}
                        >
                          <span className="field-main">
                            <span className="f-label">{field.label}</span>
                            <span className="f-context">{actionSummary(rule, needsSignoff)}</span>
                          </span>
                          <span className="f-right">
                            {needsSignoff && <span className="needs-review-mark">Needs sign-off</span>}
                            {!needsSignoff && stake && <span className="risk-note">{stake}</span>}
                            {rule?.human_override && <span className="reviewed-mark">✓ Reviewed</span>}
                            {deadline && <span className="retention-note">Delete by {deadline}</span>}
                            {rule ? <ActionBadge action={rule.action} sm /> : <span className="skeleton" style={{ width: "4.5rem" }} />}
                            <span className="chevron" aria-hidden="true">›</span>
                          </span>
                        </button>
                      );
                    })
                )}
              </div>
            </section>
          )}

          {!running && (
            <p className="review-method">
              Recommendations combine deterministic compliance checks with the AI assessment. Choosing a milder action requires a reason and is flagged in the export.
            </p>
          )}
        </main>

        {selectedField && (
          <DecisionDrawer
            field={selectedField}
            rule={selectedRule}
            check={selectedCheck}
            kb={kb}
            error={rowErrors[selectedField.field_id] || undefined}
            disabled={busy || running}
            requiresSignoff={requiresSignoff(selectedRule, selectedCheck)}
            hasPrev={selectedIndex > 0}
            hasNext={selectedIndex >= 0 && selectedIndex < flatOrder.length - 1}
            onClose={closeField}
            onStep={(delta) => setSelected(flatOrder[selectedIndex + delta] ?? selected)}
            onOverride={onOverride}
          />
        )}
      </div>
    </>
  );
}
