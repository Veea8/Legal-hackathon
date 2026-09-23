import { ACTION_LABEL, days } from "../lib/actions";
import type { CheckResult, FieldRule, KBEntry } from "../types";
import KbChips from "./KbChips";

export default function RuleDetail({ rule, check, kb }: { rule: FieldRule | undefined; check: CheckResult | undefined; kb: KBEntry[] }) {
  return (
    <div className="detail">
      {rule ? (
        <>
          <div className="detail-block">
            <h4>Why</h4>
            <p>{rule.reason}</p>
            {rule.ai_milder_suggestion && (
              <p className="muted">
                AI suggests <b>{ACTION_LABEL[rule.ai_milder_suggestion.action]}</b>: {rule.ai_milder_suggestion.justification}
              </p>
            )}
          </div>
          <div className="detail-block">
            <h4>Legal references</h4>
            <KbChips ids={rule.kb_refs} kb={kb} />
          </div>
          <div className="detail-block">
            <h4>Suggested wording</h4>
            <dl className="kv">
              <dt>Microcopy</dt><dd>{rule.microcopy ?? <span className="muted">none yet</span>}</dd>
              <dt>Label</dt><dd>{rule.suggested_label ?? <span className="muted">unchanged</span>}</dd>
              <dt>Retention</dt><dd>{days(rule.retention_days)}</dd>
              <dt>Data handling</dt><dd>{rule.data_handling}</dd>
              {rule.ai && (
                <>
                  <dt>AI category</dt>
                  <dd>{rule.ai.inferred_category}{rule.ai.special_category ? " (special category)" : ""} · necessity: {rule.ai.necessity}</dd>
                </>
              )}
            </dl>
          </div>
        </>
      ) : (
        <p className="muted">AI assessment pending.</p>
      )}
      <div className="detail-block">
        <h4>Compliance checks</h4>
        {check && check.triggered.length > 0 ? (
          <ul className="checks">
            {check.triggered.map((t) => (
              <li key={t.rule_id} className={`sev-${t.severity}`}>
                <code>{t.rule_id}</code> <span className="sev">{t.severity}</span> {t.message}
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">No compliance issue found.</p>
        )}
      </div>
    </div>
  );
}
