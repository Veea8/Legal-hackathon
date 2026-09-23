import { useState } from "react";
import { ACTIONS, ACTION_LABEL, isMilder } from "../lib/actions";
import type { Action, CheckResult, FieldSpec, KBEntry, RuleOverride, RuleSet } from "../types";
import ActionBadge from "./ActionBadge";
import RuleDetail from "./RuleDetail";

interface Props {
  fields: FieldSpec[];
  checks: CheckResult[];
  ruleset: RuleSet | null;
  kb: KBEntry[];
  rowErrors: Record<string, string>;
  disabled: boolean;
  onOverride: (o: RuleOverride) => Promise<void>;
}

interface Pending {
  action: Action;
  note: string;
}

export default function ReviewTable({ fields, checks, ruleset, kb, rowErrors, disabled, onOverride }: Props) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [pending, setPending] = useState<Record<string, Pending>>({});

  const checkById = new Map(checks.map((c) => [c.field_id, c]));
  const ruleById = new Map((ruleset?.rules ?? []).map((r) => [r.field_id, r]));

  function toggle(id: string) {
    setExpanded((s) => {
      const n = new Set(s);
      if (n.has(id)) n.delete(id); else n.add(id);
      return n;
    });
  }

  async function choose(fieldId: string, action: Action, floor: Action, current: Action) {
    if (action === current) {
      setPending((p) => { const n = { ...p }; delete n[fieldId]; return n; });
      return;
    }
    if (isMilder(action, floor)) {
      setPending((p) => ({ ...p, [fieldId]: { action, note: "" } }));
      return;
    }
    await onOverride({ field_id: fieldId, action });
  }

  async function confirm(fieldId: string) {
    const p = pending[fieldId];
    if (!p) return;
    await onOverride({ field_id: fieldId, action: p.action, note: p.note });
    setPending((s) => { const n = { ...s }; delete n[fieldId]; return n; });
  }

  return (
    <div className="table-wrap">
      <table className="review">
        <thead>
          <tr>
            <th>Field</th>
            <th>Compliance check</th>
            <th>AI assessment</th>
            <th>Proposed</th>
            <th>Alternative</th>
            <th>Warnings</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {fields.map((f) => {
            const check = checkById.get(f.field_id);
            const rule = ruleById.get(f.field_id);
            const floor = check?.floor_action ?? "keep";
            const p = pending[f.field_id];
            const shown = p?.action ?? rule?.action ?? floor;
            const aiError = ruleset?.ai_errors?.[f.field_id];
            const isOpen = expanded.has(f.field_id);
            return (
              <FragmentRow key={f.field_id}>
                <tr className={`row-${rule?.action ?? "pending"}`}>
                  <td>
                    <b>{f.label}</b>
                    <br />
                    <small className="muted">
                      <code>{f.name}</code> · {f.required ? "required" : "optional"}{f.data_category ? ` · ${f.data_category}` : ""}
                    </small>
                  </td>
                  <td>
                    {check ? (
                      <>
                        <ActionBadge action={check.floor_action} small />
                        <div className="rule-ids">
                          {check.triggered.filter((t) => t.severity !== "info").map((t) => (
                            <code key={t.rule_id} title={t.message}>{t.rule_id}</code>
                          ))}
                          {check.protected_inclusive && <span className="tag">inclusive, not penalised</span>}
                        </div>
                      </>
                    ) : <span className="muted">…</span>}
                  </td>
                  <td>
                    {rule?.ai ? (
                      <>
                        <ActionBadge action={rule.ai.proposed_action} modifiers={rule.ai.modifiers} small />
                        <div className="ai-reason">{rule.ai.reason}</div>
                        <small className="muted">confidence {Math.round(rule.ai.confidence * 100)}%</small>
                      </>
                    ) : rule ? (
                      <span className="muted" title={aiError}>{aiError ? "unavailable" : "no assessment"}</span>
                    ) : (
                      <span className="muted pending">pending…</span>
                    )}
                  </td>
                  <td>
                    <div className="proposed">
                      <select
                        aria-label={`Action for ${f.label}`}
                        value={shown}
                        disabled={disabled || !rule}
                        onChange={(e) => void choose(f.field_id, e.target.value as Action, floor, rule?.action ?? floor)}
                      >
                        {ACTIONS.map((a) => <option key={a} value={a}>{ACTION_LABEL[a]}</option>)}
                      </select>
                      {rule && rule.modifiers.length > 0 && <ActionBadge action={rule.action} modifiers={rule.modifiers} small />}
                      {rule?.disagreement && <span className="tag tag-warn" title="AI proposed a milder action than the compliance floor">disagreement</span>}
                      {rule?.human_override && <span className="tag tag-human">your decision</span>}
                    </div>
                    {p && (
                      <div className="note-box">
                        <label>
                          <span className="muted">"{ACTION_LABEL[p.action]}" is milder than the compliance floor "{ACTION_LABEL[floor]}". Note required:</span>
                          <input
                            value={p.note}
                            onChange={(e) => setPending((s) => ({ ...s, [f.field_id]: { ...p, note: e.target.value } }))}
                            placeholder="Why is this justified?"
                          />
                        </label>
                        <div className="row-actions">
                          <button type="button" disabled={disabled || !p.note.trim()} onClick={() => void confirm(f.field_id)}>Confirm</button>
                          <button type="button" className="secondary" onClick={() => setPending((s) => { const n = { ...s }; delete n[f.field_id]; return n; })}>Cancel</button>
                        </div>
                      </div>
                    )}
                    {rowErrors[f.field_id] && <div className="error inline">{rowErrors[f.field_id]}</div>}
                  </td>
                  <td>
                    {rule?.alternative_action && (
                      <button type="button" className="secondary small" disabled={disabled}
                        onClick={() => void onOverride({ field_id: f.field_id, accept_alternative: true })}>
                        Use {ACTION_LABEL[rule.alternative_action]}
                      </button>
                    )}
                    {rule?.ai_milder_suggestion && (
                      <button type="button" className="secondary small" disabled={disabled}
                        onClick={() => void onOverride({ field_id: f.field_id, accept_ai_suggestion: true })}
                        title={rule.ai_milder_suggestion.justification}>
                        Accept AI suggestion: {ACTION_LABEL[rule.ai_milder_suggestion.action]}
                      </button>
                    )}
                    {!rule?.alternative_action && !rule?.ai_milder_suggestion && <span className="muted">–</span>}
                  </td>
                  <td>
                    {rule?.warning && <mark className="warn">{rule.warning}</mark>}
                    {rule?.human_override?.note && <div><small className="muted">Note: {rule.human_override.note}</small></div>}
                  </td>
                  <td>
                    <button type="button" className="link" aria-expanded={isOpen} onClick={() => toggle(f.field_id)}>
                      {isOpen ? "Hide" : "Details"}
                    </button>
                  </td>
                </tr>
                {isOpen && (
                  <tr className="detail-row">
                    <td colSpan={7}><RuleDetail rule={rule} check={check} kb={kb} /></td>
                  </tr>
                )}
              </FragmentRow>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function FragmentRow({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
