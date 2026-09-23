import type { ReportRow } from "../types";
import ActionBadge from "./ActionBadge";

export default function ReportTable({ rows }: { rows: ReportRow[] }) {
  return (
    <div className="table-wrap">
      <table className="report">
        <thead>
          <tr>
            <th>Field</th><th>Before</th><th>Action</th><th>Reason</th><th>Legal basis</th><th>Owner decision</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.field_id} className={`row-${r.action}`}>
              <td><b>{r.label}</b><br /><small className="muted"><code>{r.field_id}</code></small></td>
              <td>{r.original_required ? "required" : "optional"}<br /><small className="muted">{r.original_category ?? ""}</small></td>
              <td><ActionBadge action={r.action} modifiers={r.modifiers} small /><br /><small className="muted">source: {r.source}</small></td>
              <td>{r.reason}</td>
              <td><small>{r.kb_titles.join("; ") || "–"}</small></td>
              <td>
                {r.owner_decision}
                {r.warning && <div><mark className="warn">{r.warning}</mark></div>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
