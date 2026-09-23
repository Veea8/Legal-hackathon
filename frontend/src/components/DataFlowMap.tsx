import { ACTION_LABEL } from "../lib/actions";
import type { Action, FormSchema, ReportRow } from "../types";

export default function DataFlowMap({ schema, rows }: { schema: FormSchema; rows: ReportRow[] }) {
  const actionById = new Map<string, Action>(rows.map((r) => [r.field_id, r.action]));
  const groups = new Map<string, typeof schema.fields>();
  for (const f of schema.fields) {
    const dest = f.destination || "unspecified system";
    if (!groups.has(dest)) groups.set(dest, []);
    groups.get(dest)!.push(f);
  }
  return (
    <div className="flow">
      <div className="flow-source">
        <b>{schema.name}</b>
        <br /><small className="muted">{schema.fields.length} fields collected</small>
      </div>
      <div className="flow-arrow" aria-hidden="true">→</div>
      <div className="flow-systems">
        {[...groups.entries()].map(([dest, fields]) => (
          <div key={dest} className="flow-system">
            <h4>{dest}</h4>
            <ul>
              {fields.map((f) => {
                const a = actionById.get(f.field_id) ?? "keep";
                const gone = a === "remove";
                return (
                  <li key={f.field_id} className={`flow-field flow-${a}`} title={ACTION_LABEL[a]}>
                    {gone ? <s>{f.label}</s> : f.label}
                    {f.third_party_shared && <span className="tag tag-third">3rd party</span>}
                    {f.sensitive && <span className="tag">sensitive</span>}
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}
