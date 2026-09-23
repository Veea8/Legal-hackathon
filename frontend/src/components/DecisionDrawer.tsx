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
  requiresSignoff: boolean;
  hasPrev: boolean;
  hasNext: boolean;
  onClose: () => void;
  onStep: (delta: number) => void;
  onOverride: (override: RuleOverride) => Promise<void>;
}

const SOURCE_LABEL: Record<string, string> = {
  checks: "Compliance check",
  ai: "AI assessment",
  both: "Check and AI agree",
  human: "Your decision",
};

export default function DecisionDrawer(props: Props) {
  const { field, rule, check, kb, disabled, onClose } = props;
  const floor = check?.floor_action ?? "keep";
  const current = rule?.action ?? floor;
  const signedOff = Boolean(rule?.human_override);

  const [pending, setPending] = useState<{ action: Action; note: string } | null>(null);
  const [limit, setLimit] = useState<number | "">(rule?.retention_days ?? "");
  const [showAlternatives, setShowAlternatives] = useState(false);
  const titleRef = useRef<HTMLHeadingElement | null>(null);

  useEffect(() => {
    setPending(null);
    setLimit(rule?.retention_days ?? "");
    setShowAlternatives(false);
    titleRef.current?.focus();
  }, [field.field_id, rule?.retention_days]);

  useEffect(() => {
    document.body.classList.add("drawer-open");
    return () => document.body.classList.remove("drawer-open");
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const consequence = consequenceFor(rule, check);
  const blocked = (check?.triggered ?? []).some((item) => item.severity === "block");
  const timeLimited = rule?.retention_days != null && rule.action !== "remove";
  const deadline = deadlineFrom(typeof limit === "number" ? limit : null);

  async function choose(action: Action) {
    const shown = pending?.action ?? current;
    if (action === shown) {
      if (action === current && props.requiresSignoff && !signedOff) {
        await props.onOverride({ field_id: field.field_id, action });
      }
      return;
    }
    if (action === current) {
      setPending(null);
      return;
    }
    if (isMilder(action, floor)) {
      setPending({ action, note: "" });
      return;
    }
    setPending(null);
    await props.onOverride({ field_id: field.field_id, action });
  }

  async function confirmPending() {
    if (!pending?.note.trim()) return;
    await props.onOverride({ field_id: field.field_id, action: pending.action, note: pending.note });
    setPending(null);
  }

  async function saveLimit(value: number | null) {
    setLimit(value ?? "");
    await props.onOverride(
      value === null
        ? { field_id: field.field_id, clear_retention: true }
        : { field_id: field.field_id, retention_days: value },
    );
  }

  return (
    <>
      <button type="button" className="drawer-backdrop" aria-label="Close field review" onClick={props.onClose} />
      <aside className="drawer" role="dialog" aria-labelledby="decision-title">
        <header className="drawer-head">
          <div className="dh-top">
            <div>
              <span className="panel-kicker">Field decision</span>
              <h2 id="decision-title" ref={titleRef} tabIndex={-1}>{field.label}</h2>
            </div>
            <button type="button" className="drawer-close" onClick={props.onClose} aria-label="Close">×</button>
          </div>
          <div className="decision-status">
            <ActionBadge action={current} modifiers={rule?.modifiers} />
            {signedOff && <span className="reviewed-mark">✓ Reviewed</span>}
            {rule?.ai?.special_category && <span className="tag tag-warn">Special category</span>}
            {timeLimited && <span className="tag tag-ok">Time-limited</span>}
          </div>
        </header>

        <div className="drawer-body">
          {!rule ? (
            <p className="muted">Assessment still running for this field…</p>
          ) : (
            <>
              <section className={`decision-card${props.requiresSignoff && !signedOff ? " unresolved" : ""}`}>
                <span className="decision-kicker">Recommended decision</span>
                <div className="decision-recommendation">
                  <span className="decision-icon" aria-hidden="true">{ACTION_ICON[current]}</span>
                  <div>
                    <h3>{ACTION_LABEL[current]}</h3>
                    <p>{ACTION_HELP[current]}</p>
                  </div>
                </div>

                {props.requiresSignoff && !signedOff ? (
                  <button type="button" className="block" disabled={disabled} onClick={() => void choose(current)}>
                    Confirm recommendation
                  </button>
                ) : signedOff ? (
                  <div className="decision-recorded">
                    <span>✓ Decision recorded</span>
                    <button type="button" className="link" disabled={disabled} onClick={() => void props.onOverride({ field_id: field.field_id })}>
                      Reset
                    </button>
                  </div>
                ) : null}

                <button
                  type="button"
                  className="ghost block alternatives-toggle"
                  aria-expanded={showAlternatives}
                  onClick={() => setShowAlternatives((open) => !open)}
                >
                  {showAlternatives ? "Hide other options" : signedOff ? "Change decision" : "Choose a different action"}
                </button>

                {showAlternatives && (
                  <div className="decide-list">
                    {ACTIONS.filter((action) => action !== current).map((action) => (
                      <button
                        key={action}
                        type="button"
                        className="decide-opt"
                        aria-pressed={pending?.action === action}
                        disabled={disabled}
                        onClick={() => void choose(action)}
                      >
                        <span className="radio" aria-hidden="true" />
                        <span>
                          <span className="o-title"><span aria-hidden="true">{ACTION_ICON[action]}</span>{ACTION_LABEL[action]}</span>
                          <span className="o-sub">{ACTION_HELP[action]}</span>
                        </span>
                      </button>
                    ))}
                  </div>
                )}

                {pending && (
                  <div className="note-box">
                    <p>
                      <b>{ACTION_LABEL[pending.action]}</b> is milder than the compliance floor <b>{ACTION_LABEL[floor]}</b>.
                      Add the reason that should appear in the report.
                    </p>
                    <input
                      autoFocus
                      value={pending.note}
                      aria-label="Reason for choosing a milder action"
                      placeholder="e.g. Required by our insurer under contract X"
                      onChange={(event) => setPending({ ...pending, note: event.target.value })}
                    />
                    <div className="row" style={{ marginTop: ".5rem" }}>
                      <button type="button" className="sm" disabled={disabled || !pending.note.trim()} onClick={() => void confirmPending()}>
                        Confirm and flag
                      </button>
                      <button type="button" className="ghost sm" onClick={() => setPending(null)}>Cancel</button>
                    </div>
                  </div>
                )}

                {rule.ai_milder_suggestion && !signedOff && (
                  <button
                    type="button"
                    className="ai-alternative"
                    disabled={disabled}
                    onClick={() => void props.onOverride({ field_id: field.field_id, accept_ai_suggestion: true })}
                    title={rule.ai_milder_suggestion.justification}
                  >
                    Use the AI’s alternative: {ACTION_LABEL[rule.ai_milder_suggestion.action]} →
                  </button>
                )}
                {props.error && <div className="error inline">{props.error}</div>}
              </section>

              <section className="decision-explainer">
                <div>
                  <h4>Why this matters</h4>
                  <p>{rule.reason}</p>
                </div>
                <div>
                  <h4>What changes</h4>
                  <p>
                    {ACTION_HELP[current]}
                    {rule.modifiers.length > 0 && ` Apply it ${rule.modifiers.map((modifier) => MODIFIER_LABEL[modifier]).join(", ")}.`}
                  </p>
                </div>
              </section>

              {(rule.microcopy || rule.suggested_label) && rule.action !== "remove" && (
                <section className="dsec wording-card">
                  <h4>Suggested wording</h4>
                  <dl className="dl">
                    {rule.suggested_label && <><dt>Label</dt><dd>{rule.suggested_label}</dd></>}
                    {rule.microcopy && <><dt>Under the field</dt><dd>“{rule.microcopy}”</dd></>}
                  </dl>
                </section>
              )}

              <section className="dsec">
                <h4>How long do you keep it?</h4>
                {rule.action === "remove" ? (
                  <p className="small muted">Nothing is collected, so there is nothing to retain.</p>
                ) : (
                  <div className="decide-list retention-choices">
                    <button
                      type="button"
                      className="decide-opt"
                      aria-pressed={limit === ""}
                      disabled={disabled}
                      onClick={() => limit !== "" && void saveLimit(null)}
                    >
                      <span className="radio" aria-hidden="true" />
                      <span>
                        <span className="o-title"><span aria-hidden="true">∞</span>Keep without a deadline</span>
                        <span className="o-sub">The data stays until someone removes it manually.</span>
                      </span>
                    </button>
                    <button
                      type="button"
                      className="decide-opt"
                      aria-pressed={limit !== ""}
                      disabled={disabled}
                      onClick={() => limit === "" && void saveLimit(rule.ai?.retention_suggestion_days ?? field.retention_days ?? 365)}
                    >
                      <span className="radio" aria-hidden="true" />
                      <span>
                        <span className="o-title"><span aria-hidden="true">⏱</span>Delete automatically</span>
                        <span className="o-sub">Set a deadline that will also appear in the report.</span>
                      </span>
                    </button>
                  </div>
                )}

                {rule.action !== "remove" && limit !== "" && (
                  <div className="timebox">
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
                      {RETENTION_PRESETS.map((preset) => (
                        <button
                          key={preset.days}
                          type="button"
                          className={limit === preset.days ? "on" : undefined}
                          disabled={disabled}
                          onClick={() => void saveLimit(preset.days)}
                        >
                          {preset.label}
                        </button>
                      ))}
                    </div>
                    {deadline && <div className="deadline">Collected today → delete by {deadline}</div>}
                  </div>
                )}
              </section>

              <details className="evidence">
                <summary>Evidence and details</summary>
                <div className="evidence-body">
                  <div className="evidence-tags">
                    <span className="tag">{SOURCE_LABEL[rule.source] ?? rule.source}</span>
                    {rule.ai && <span className="tag">{Math.round(rule.ai.confidence * 100)}% AI confidence</span>}
                    {blocked && <span className="tag tag-warn">Blocking compliance issue</span>}
                  </div>

                  <section className="dsec">
                    <h4>Impact</h4>
                    <div className={`consequence${consequence.severity === "high" ? "" : " mild"}`}>
                      <b>If you ignore the recommendation</b>
                      {consequence.risk}
                    </div>
                    <div className="benefit"><b>If you follow it</b>{consequence.benefit}</div>
                  </section>

                  <section className="dsec">
                    <h4>Legal references</h4>
                    <KbChips ids={rule.kb_refs} kb={kb} max={3} />
                  </section>

                  {check && check.triggered.length > 0 && (
                    <section className="dsec">
                      <h4>Compliance checks</h4>
                      <ul className="checklist">
                        {check.triggered.map((item) => (
                          <li key={item.rule_id} className={`sev-${item.severity}`}>
                            {item.message}<span className="sev">{item.rule_id} · {item.severity}</span>
                          </li>
                        ))}
                      </ul>
                    </section>
                  )}

                  <section className="dsec">
                    <h4>As collected today</h4>
                    <dl className="dl">
                      <dt>Field</dt><dd><code>{field.name}</code> · {field.type} · {field.required ? "required" : "optional"}</dd>
                      <dt>Category</dt><dd>{field.data_category || "not stated"}</dd>
                      <dt>Purpose</dt><dd>{field.purpose_text?.trim() || <span className="faint">none stated</span>}</dd>
                      <dt>Retention</dt><dd>{days(field.retention_days)}</dd>
                      <dt>Goes to</dt><dd>{field.destination || "not stated"}{field.third_party_shared ? " · shared with a third party" : ""}</dd>
                    </dl>
                  </section>
                </div>
              </details>
            </>
          )}
        </div>

        <footer className="drawer-foot">
          <button type="button" className="ghost sm" disabled={!props.hasPrev} onClick={() => props.onStep(-1)}>← Previous</button>
          <button type="button" className="ghost sm" disabled={!props.hasNext} onClick={() => props.onStep(1)}>Next →</button>
          <span className="grow" />
          <button type="button" className="sm" onClick={props.onClose}>Done</button>
        </footer>
      </aside>
    </>
  );
}
