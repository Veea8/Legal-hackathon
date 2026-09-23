import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError, api, errorMessage } from "../api";
import ActionBadge from "../components/ActionBadge";
import DecisionDrawer from "../components/DecisionDrawer";
import { ACTION_SHORT, days, deadlineFrom } from "../lib/actions";
import { stakeLine } from "../lib/consequences";
import type { Action, CheckResult, FieldRule, FieldSpec, FormSchema, KBEntry, RuleOverride, RuleSet } from "../types";

type GroupKey = "decide" | Action;

/* Order is the reading order: what a human must settle first, then strictest to mildest.
   Every group carries its own colour so the page can be read at a glance. */
const GROUPS: { key: GroupKey; title: string; sub: string; verb: string }[] = [
  { key: "decide", title: "Needs your decision", sub: "A human has to sign this off — the law does not decide it for you.", verb: "Decide" },
  { key: "remove", title: "Do not collect", sub: "These fields disappear from the form.", verb: "Remove" },
  { key: "make_optional", title: "Make optional", sub: "Still asked, but nobody is forced to answer.", verb: "Optional" },
  { key: "better_explain", title: "Explain why you ask", sub: "Keep the field, add one sentence underneath.", verb: "Explain" },
  { key: "keep", title: "Keep as is", sub: "Necessary, proportionate, nothing to change.", verb: "Keep" },
];

const ORDER: Action[] = ["remove", "make_optional", "better_explain", "keep"];

/** A field is a human decision when the two assessments disagree or a check blocks it outright —
    until a human has ruled on it. A missing AI key is not a decision, it is a footnote. */
function needsDecision(rule: FieldRule | undefined, check: CheckResult | undefined): boolean {
  if (!rule || rule.human_override) return false;
  if (rule.disagreement || rule.ai_milder_suggestion) return true;
  return (check?.triggered ?? []).some((t) => t.severity === "block");
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
  const [openGroups, setOpenGroups] = useState<Set<GroupKey>>(new Set(["decide", "remove", "make_optional"]));
  const [selected, setSelected] = useState<string | null>(null);
  const [focusTime, setFocusTime] = useState(false);
  const groupRefs = useRef<Partial<Record<GroupKey, HTMLElement | null>>>({});

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.getForm(id), api.checks(id), api.kb()])
      .then(([f, c, k]) => {
        if (cancelled) return;
        setSchema(f);
        setChecks(c);
        setKb(k);
      })
      .catch((e) => !cancelled && setError(errorMessage(e)));
    return () => { cancelled = true; };
  }, [id]);

  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;
    async function tick() {
      try {
        let rs: RuleSet;
        try {
          rs = await api.analysis(id);
        } catch (e) {
          if (e instanceof ApiError && e.status === 404) rs = await api.analyze(id, false);
          else throw e;
        }
        if (cancelled) return;
        setRuleset(rs);
        if (rs.status === "running") timer = window.setTimeout(() => void tick(), 900);
      } catch (e) {
        if (!cancelled) setError(errorMessage(e));
      }
    }
    void tick();
    return () => { cancelled = true; if (timer) window.clearTimeout(timer); };
  }, [id]);

  const onOverride = useCallback(async (o: RuleOverride) => {
    setRowErrors((r) => ({ ...r, [o.field_id]: "" }));
    try {
      setRuleset(await api.putRules(id, [o]));
    } catch (e) {
      setRowErrors((r) => ({ ...r, [o.field_id]: errorMessage(e) }));
    }
  }, [id]);

  const checkById = useMemo(() => new Map(checks.map((c) => [c.field_id, c])), [checks]);
  const ruleById = useMemo(() => new Map((ruleset?.rules ?? []).map((r) => [r.field_id, r])), [ruleset]);

  const grouped = useMemo(() => {
    const out = new Map<GroupKey, FieldSpec[]>(GROUPS.map((g) => [g.key, [] as FieldSpec[]]));
    for (const f of schema?.fields ?? []) {
      const rule = ruleById.get(f.field_id);
      const key: GroupKey = needsDecision(rule, checkById.get(f.field_id)) ? "decide" : (rule?.action ?? "keep");
      out.get(key)!.push(f);
    }
    return out;
  }, [schema, ruleById, checkById]);

  /** Flat order across the visible groups, so "next field" in the drawer follows the page. */
  const flatOrder = useMemo(
    () => GROUPS.flatMap((g) => (grouped.get(g.key) ?? []).map((f) => f.field_id)),
    [grouped],
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

  function toggleGroup(key: GroupKey) {
    setOpenGroups((s) => {
      const n = new Set(s);
      if (n.has(key)) n.delete(key); else n.add(key);
      return n;
    });
  }

  /** Legend click: open the group and bring it into view. */
  function jumpTo(key: GroupKey) {
    setOpenGroups((s) => new Set(s).add(key));
    window.requestAnimationFrame(() => groupRefs.current[key]?.scrollIntoView({ behavior: "smooth", block: "start" }));
  }

  function openField(fieldId: string, atTimeLimit = false) {
    setFocusTime(atTimeLimit);
    setSelected(fieldId);
  }

  if (!schema) return error ? <div className="error" role="alert">{error}</div> : <p className="muted">Loading…</p>;

  const running = !ruleset || ruleset.status === "running";
  const nDecide = grouped.get("decide")?.length ?? 0;
  const counts = ORDER.reduce<Record<Action, number>>(
    (acc, a) => ({ ...acc, [a]: (ruleset?.rules ?? []).filter((r) => r.action === a).length }),
    { keep: 0, better_explain: 0, make_optional: 0, remove: 0 },
  );
  const nErrors = ruleset ? Object.keys(ruleset.ai_errors).length : 0;
  const nTimed = (ruleset?.rules ?? []).filter((r) => r.action !== "remove" && r.retention_days != null).length;
  const selectedField = schema.fields.find((f) => f.field_id === selected);
  const selIndex = selected ? flatOrder.indexOf(selected) : -1;
  const total = schema.fields.length;

  return (
    <>
      <div className="review-head">
        <div>
          <h1>{schema.name}</h1>
          <p className="muted small">
            {total} fields · {schema.business_context} ·{" "}
            <Link to={`/forms/${id}/context`}>change the context</Link>
          </p>
        </div>
        <div className="row">
          {running && (
            <span className="tag tag-warn">
              <i className="tag-dot pulse" /> Assessing {ruleset ? `${ruleset.fields_done}/${ruleset.fields_total}` : ""}
            </span>
          )}
          {!running && ruleset && (
            <span className="tag tag-live">{ruleset.cached ? "cached result" : ruleset.ai_model ?? "checks only"}</span>
          )}
          <button type="button" onClick={() => void applyRules()} disabled={busy || running}>
            {busy ? "Applying…" : "Apply and export →"}
          </button>
        </div>
      </div>

      {error && <div className="error" role="alert">{error}</div>}

      {/* The whole form in one line of colour, then the same colours all the way down the page. */}
      {!running && ruleset && (
        <div className="legend-wrap">
          <div className="legend-bar" role="img" aria-label="Recommendations across all fields">
            {GROUPS.map((g) => {
              const n = grouped.get(g.key)?.length ?? 0;
              if (n === 0) return null;
              return <i key={g.key} className={`seg a-${g.key}`} style={{ flexGrow: n }} title={`${g.title}: ${n}`} />;
            })}
          </div>
          <div className="legend">
            {GROUPS.map((g) => {
              const n = grouped.get(g.key)?.length ?? 0;
              if (n === 0) return null;
              return (
                <button key={g.key} type="button" className={`leg a-${g.key}`} onClick={() => jumpTo(g.key)}>
                  <i className="swatch" aria-hidden="true" />
                  <b>{n}</b> {g.verb}
                </button>
              );
            })}
            {nTimed > 0 && (
              <span className="leg timed">
                <i className="swatch" aria-hidden="true" />
                <b>{nTimed}</b> time-limited
              </span>
            )}
          </div>
        </div>
      )}

      {nDecide > 0 && !running && (
        <div className="callout">
          <span className="ci" aria-hidden="true">⚑</span>
          <div>
            <h3>{nDecide} field{nDecide === 1 ? "" : "s"} need{nDecide === 1 ? "s" : ""} a human decision</h3>
            <p>
              The checks and the assessment point in different directions, or the law leaves the call to you.
              Open each one, read what it costs to get it wrong, and decide. Nothing is applied until you do.
            </p>
          </div>
        </div>
      )}
      {nErrors > 0 && (
        <div className="callout info">
          <span className="ci" aria-hidden="true">⚠</span>
          <div>
            <h3>The AI was unavailable for {nErrors} field{nErrors === 1 ? "" : "s"}</h3>
            <p>The deterministic compliance checks still ran, and their results stand for those fields.</p>
          </div>
        </div>
      )}

      <div className="review-layout">
        {GROUPS.map((g) => {
          const fields = grouped.get(g.key) ?? [];
          if (fields.length === 0) return null;
          const open = openGroups.has(g.key);
          return (
            <section
              key={g.key}
              ref={(el) => { groupRefs.current[g.key] = el; }}
              className={`group a-${g.key}${g.key === "decide" ? " decide" : ""}`}
            >
              <button type="button" className="group-head" aria-expanded={open} onClick={() => toggleGroup(g.key)}>
                <span className="caret" aria-hidden="true">▶</span>
                <span>
                  <span className="g-title">
                    {g.key === "decide" && <span aria-hidden="true">⚑ </span>}
                    {g.title}
                  </span>
                  <span className="g-sub" style={{ display: "block" }}>{g.sub}</span>
                </span>
                <span className="count">{fields.length}</span>
              </button>

              {open && (
                <div className="field-list">
                  {fields.map((f) => {
                    const rule = ruleById.get(f.field_id);
                    const check = checkById.get(f.field_id);
                    const stake = stakeLine(rule, check);
                    const canExpire = rule != null && rule.action !== "remove";
                    const deadline = canExpire ? deadlineFrom(rule!.retention_days) : null;
                    return (
                      <div
                        key={f.field_id}
                        className={`field-row a-${g.key}${selected === f.field_id ? " selected" : ""}${rule ? "" : " pending"}`}
                      >
                        <button type="button" className="f-open" onClick={() => openField(f.field_id)}>
                          <span className="f-label">{f.label}</span>
                          <span className="f-meta">
                            <code>{f.name}</code>
                            <span>· {f.required ? "required" : "optional"}</span>
                            {f.data_category && <span>· {f.data_category}</span>}
                            {!f.purpose_text?.trim() && <span>· no purpose stated</span>}
                          </span>
                        </button>
                        <div className="f-right">
                          {stake && <span className="tag tag-warn">{stake}</span>}
                          {rule?.human_override && <span className="tag tag-accent">your call</span>}
                          {rule ? <ActionBadge action={rule.action} sm /> : <span className="skeleton" style={{ width: "4.5rem" }} />}
                          {/* Expiry is a decision in its own right, so it gets its own control here
                              instead of hiding one drawer-scroll away. */}
                          {canExpire && (
                            <button
                              type="button"
                              className={`expiry${deadline ? " set" : ""}`}
                              disabled={busy}
                              onClick={() => openField(f.field_id, true)}
                              title={deadline ? `Has to be deleted by ${deadline}` : "No deletion deadline set"}
                            >
                              <span aria-hidden="true">⏱</span>
                              {deadline ? `delete by ${deadline}` : "set expiry"}
                            </button>
                          )}
                          <button type="button" className="chevron" aria-label={`Open ${f.label}`} onClick={() => openField(f.field_id)}>›</button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </section>
          );
        })}
      </div>

      {ruleset && !running && (
        <p className="tiny faint" style={{ marginTop: "1.25rem" }}>
          {ORDER.map((a) => `${ACTION_SHORT[a]} ${counts[a]}`).join(" · ")} · default retention from your context:{" "}
          {days(schema.retention_default_days)}. A recommendation is the stricter of the compliance check and the AI
          assessment; going milder is allowed, needs a reason, and is flagged in the export.
        </p>
      )}

      {selectedField && (
        <DecisionDrawer
          field={selectedField}
          rule={ruleById.get(selectedField.field_id)}
          check={checkById.get(selectedField.field_id)}
          kb={kb}
          error={rowErrors[selectedField.field_id] || undefined}
          disabled={busy || running}
          hasPrev={selIndex > 0}
          hasNext={selIndex >= 0 && selIndex < flatOrder.length - 1}
          focusTime={focusTime}
          onClose={() => setSelected(null)}
          onStep={(d) => { setFocusTime(false); setSelected(flatOrder[selIndex + d] ?? selected); }}
          onOverride={onOverride}
        />
      )}
    </>
  );
}
