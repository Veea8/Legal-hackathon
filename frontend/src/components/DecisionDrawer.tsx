import { useEffect, useRef, useState } from "react";
import { ACTIONS, ACTION_HELP, ACTION_ICON, ACTION_LABEL, MODIFIER_LABEL, RETENTION_PRESETS, days, deadlineFrom, isMilder } from "../lib/actions";
import { consequenceFor } from "../lib/consequences";
import type { Action, CheckResult, FieldSpec, FieldRule, KBEntry, RuleOverride } from "../types";
import ActionBadge from "./ActionBadge";
import KbChips from "./KbChips";

interface Props {
  field: FieldSpec;
  rule: FieldRule | undefined;
  check: CheckResult | undefined;
  kb: KBEntry[];
  error?: string;
  disabled: boolean;
  hasPrev: boolean;
  hasNext: boolean;
  /** Opened from the expiry control on the row: scroll straight to the time limit. */
  focusTime?: boolean;
  onClose: () => void;
  onStep: (delta: number) => void;
  onOverride: (o: RuleOverride) => Promise<void>;
}

const SOURCE_LABEL: Record<string, string> = {
  checks: "Compliance check",
  ai: "AI assessment",
  both: "Check + AI agree",
  human: "Your decision",
};

export default function DecisionDrawer(p: Props) {
  const { field, rule, check, kb, disabled, onClose } = p;
  const floor = check?.floor_action ?? "keep";
  const current = rule?.action ?? floor;

  const [pending, setPending] = useState<{ action: Action; note: string } | null>(null);
  const [limit, setLimit] = useState<number | "">(rule?.retention_days ?? "");
  const timeRef = useRef<HTMLElement | null>(null);

  // The drawer is reused for the next field: reset the local editing state.
  useEffect(() => {
    setPending(null);
    setLimit(rule?.retention_days ?? "");
  }, [field.field_id, rule?.retention_days]);

  useEffect(() => {
    if (!p.focusTime || !rule) return;
    const t = window.setTimeout(() => timeRef.current?.scrollIntoView({ behavior: "smooth", block: "center" }), 60);
    return () => window.clearTimeout(t);
  }, [p.focusTime, field.field_id, rule]);

  // Keep the page behind the drawer out of the way without blacking it out.
  useEffect(() => {
    document.body.classList.add("drawer-open");
    return () => document.body.classList.remove("drawer-open");
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const consequence = consequenceFor(rule, check);
  const blocked = (check?.triggered ?? []).some((t) => t.severity === "block");
  const timeLimited = rule?.retention_days != null && rule.action !== "remove";
  const deadline = deadlineFrom(typeof limit === "number" ? limit : null);

  async function choose(action: Action) {
    if (action === current) return;
    if (isMilder(action, floor)) {
      setPending({ action, note: "" });
      return;
    }
    setPending(null);
    await p.onOverride({ field_id: field.field_id, action });
  }

  async function confirmPending() {
    if (!pending?.note.trim()) return;
    await p.onOverride({ field_id: field.field_id, action: pending.action, note: pending.note });
    setPending(null);
  }

  async function saveLimit(value: number | null) {
    setLimit(value ?? "");
    await p.onOverride(
      value === null
        ? { field_id: field.field_id, clear_retention: true }
        : { field_id: field.field_id, retention_days: value },
    );
  }

  return (
    <>
      <button type="button" className="drawer-backdrop" aria-label="Close details" onClick={p.onClose} />
      <aside className="drawer" role="dialog" aria-label={`Decision for ${field.label}`}>
        <header className="drawer-head">
          <div className="dh-top">
            <div>
              <h2>{field.label}</h2>
              <div className="dh-meta">
                <code>{field.name}</code>
                <span>· {field.type}</span>
                <span>· {field.required ? "required today" : "optional today"}</span>
                {field.data_category && <span>· {field.data_category}</span>}
              </div>
            </div>
            <button type="button" className="drawer-close" onClick={p.onClose} aria-label="Close">✕</button>
          </div>
          <div className="row" style={{ marginTop: ".7rem" }}>
            <ActionBadge action={current} modifiers={rule?.modifiers} />
            {rule && <span className="tag">{SOURCE_LABEL[rule.source] ?? rule.source}</span>}
            {rule?.ai && <span className="tag">{Math.round(rule.ai.confidence * 100)}% confident</span>}
            {rule?.ai?.special_category && <span className="tag tag-warn">Special category</span>}
            {timeLimited && <span className="tag tag-ok">Time-limited</span>}
          </div>
        </header>

        <div className="drawer-body">
          {!rule ? (
            <p className="muted">Assessment still running for this field…</p>
          ) : (
            <>
              <section className="dsec">
                <h4>Why</h4>
                <p>{rule.reason}</p>
                {rule.modifiers.length > 0 && (
                  <p className="small muted" style={{ marginTop: ".35rem" }}>
                    With: {rule.modifiers.map((m) => MODIFIER_LABEL[m]).join(", ")}.
                  </p>
                )}
              </section>

              <section className="dsec">
                <h4>What it costs you to ignore this</h4>
                <div className={`consequence${consequence.severity === "high" ? "" : " mild"}`}>
                  <b>If you leave it as it is</b>
                  {consequence.risk}
                </div>
                <div className="benefit">
                  <b>If you follow the recommendation</b>
                  {consequence.benefit}
                </div>
              </section>

              <section className="dsec">
                <h4>Your decision</h4>
                {blocked && (
                  <p className="small" style={{ color: "var(--remove)", marginBottom: ".5rem" }}>
                    The compliance floor for this field is <b>{ACTION_LABEL[floor]}</b>. Anything milder needs a written
                    reason and is flagged in the report.
                  </p>
                )}
                <div className="decide-list">
                  {ACTIONS.map((a) => (
                    <button
                      key={a}
                      type="button"
                      className="decide-opt"
                      aria-pressed={(pending?.action ?? current) === a}
                      disabled={disabled}
                      onClick={() => void choose(a)}
                    >
                      <span className="radio" aria-hidden="true" />
                      <span>
                        <span className="o-title">
                          <span aria-hidden="true">{ACTION_ICON[a]}</span>
                          {ACTION_LABEL[a]}
                          {rule.proposed_action === a && <span className="rec">recommended</span>}
                        </span>
                        <span className="o-sub">{ACTION_HELP[a]}</span>
                      </span>
                    </button>
                  ))}
                </div>

                {pending && (
                  <div className="note-box">
                    <p>
                      <b>{ACTION_LABEL[pending.action]}</b> is milder than the compliance floor
                      <b> {ACTION_LABEL[floor]}</b>. Say why — it goes into the report as your decision.
                    </p>
                    <input
                      autoFocus
                      value={pending.note}
                      placeholder="e.g. required by our insurer under contract X"
                      onChange={(e) => setPending({ ...pending, note: e.target.value })}
                    />
                    <div className="row" style={{ marginTop: ".5rem" }}>
                      <button type="button" className="sm" disabled={disabled || !pending.note.trim()} onClick={() => void confirmPending()}>
                        Confirm and flag
                      </button>
                      <button type="button" className="ghost sm" onClick={() => setPending(null)}>Cancel</button>
                    </div>
                  </div>
                )}

                {rule.ai_milder_suggestion && !rule.human_override && (
                  <button
                    type="button"
                    className="ghost sm"
                    style={{ marginTop: ".6rem" }}
                    disabled={disabled}
                    onClick={() => void p.onOverride({ field_id: field.field_id, accept_ai_suggestion: true })}
                    title={rule.ai_milder_suggestion.justification}
                  >
                    Take the AI's milder view: {ACTION_LABEL[rule.ai_milder_suggestion.action]}
                  </button>
                )}

                {rule.human_override && (
                  <p className="small muted" style={{ marginTop: ".6rem" }}>
                    Your note: “{rule.human_override.note}” ·{" "}
                    <button type="button" className="link" disabled={disabled} onClick={() => void p.onOverride({ field_id: field.field_id })}>
                      reset to the recommendation
                    </button>
                  </p>
                )}

                {p.error && <div className="error inline">{p.error}</div>}
              </section>

              {rule.action !== "remove" && (
                <section className={`dsec${p.focusTime ? " flash" : ""}`} ref={timeRef}>
                  <h4>Time limit</h4>
                  <div className="timebox">
                    <div className="tb-head">
                      <span className="tb-title">Delete this field's data automatically</span>
                      <button
                        type="button"
                        className="switch"
                        role="switch"
                        aria-checked={limit !== ""}
                        aria-label="Set a deletion deadline"
                        disabled={disabled}
                        onClick={() => void saveLimit(limit === "" ? (rule.ai?.retention_suggestion_days ?? field.retention_days ?? 365) : null)}
                      />
                    </div>
                    {limit !== "" ? (
                      <>
                        <div className="tb-row">
                          <input
                            type="number"
                            min={1}
                            max={36500}
                            value={limit}
                            disabled={disabled}
                            onChange={(e) => setLimit(e.target.value === "" ? "" : Number(e.target.value))}
                            onBlur={() => typeof limit === "number" && limit > 0 && void saveLimit(limit)}
                          />
                          <span className="small muted">days after collection</span>
                        </div>
                        <div className="presets">
                          {RETENTION_PRESETS.map((r) => (
                            <button key={r.days} type="button" disabled={disabled} onClick={() => void saveLimit(r.days)}>{r.label}</button>
                          ))}
                        </div>
                        {deadline && <div className="deadline">Collected today ⇒ has to be deleted by {deadline}</div>}
                      </>
                    ) : (
                      <p className="small muted" style={{ marginTop: ".4rem" }}>
                        No deadline set — the data stays until someone deletes it by hand.
                        {rule.ai?.retention_suggestion_days != null && ` The assessment suggests ${days(rule.ai.retention_suggestion_days)}.`}
                      </p>
                    )}
                  </div>
                </section>
              )}

              <section className="dsec">
                <h4>Legal references</h4>
                <KbChips ids={rule.kb_refs} kb={kb} max={3} />
              </section>

              {check && check.triggered.length > 0 && (
                <section className="dsec">
                  <h4>What the checks found</h4>
                  <ul className="checklist">
                    {check.triggered.map((t) => (
                      <li key={t.rule_id} className={`sev-${t.severity}`}>
                        {t.message}
                        <span className="sev">{t.rule_id} · {t.severity}</span>
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              {(rule.microcopy || rule.suggested_label) && rule.action !== "remove" && (
                <section className="dsec">
                  <h4>Suggested wording</h4>
                  <dl className="dl">
                    {rule.suggested_label && <><dt>Label</dt><dd>{rule.suggested_label}</dd></>}
                    {rule.microcopy && <><dt>Under the field</dt><dd>“{rule.microcopy}”</dd></>}
                  </dl>
                </section>
              )}

              <section className="dsec">
                <h4>As collected today</h4>
                <dl className="dl">
                  <dt>Purpose</dt><dd>{field.purpose_text?.trim() || <span className="faint">none stated — this is what makes most fields indefensible</span>}</dd>
                  <dt>Retention</dt><dd>{days(field.retention_days)}</dd>
                  <dt>Goes to</dt><dd>{field.destination || "not stated"}{field.third_party_shared ? " · shared with a third party" : ""}</dd>
                </dl>
              </section>
            </>
          )}
        </div>

        <footer className="drawer-foot">
          <button type="button" className="ghost sm" disabled={!p.hasPrev} onClick={() => p.onStep(-1)}>← Previous</button>
          <button type="button" className="ghost sm" disabled={!p.hasNext} onClick={() => p.onStep(1)}>Next field →</button>
          <span className="grow" />
          <button type="button" className="sm" onClick={p.onClose}>Done</button>
        </footer>
      </aside>
    </>
  );
}
