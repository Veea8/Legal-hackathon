import type { DelayedField, FieldSpec, MinimisedField, RemovedField } from "../types";

type AnyField = FieldSpec | MinimisedField;

function MockInput({ f }: { f: AnyField }) {
  const common = { disabled: true, "aria-label": f.label };
  switch (f.type) {
    case "textarea":
      return <textarea {...common} rows={2} />;
    case "dropdown":
      return <select {...common}><option>Select…</option></select>;
    case "file":
      return <input {...common} type="file" />;
    case "oauth":
      return <button type="button" disabled className="secondary small">Connect…</button>;
    case "checkbox":
      return <input {...common} type="checkbox" />;
    case "date":
      return <input {...common} type="date" />;
    case "number":
      return <input {...common} type="number" />;
    default:
      return <input {...common} type="text" />;
  }
}

export default function FormPreview({
  title, fields, removed = [], delayed = [], hint,
}: { title: string; fields: AnyField[]; removed?: RemovedField[]; delayed?: DelayedField[]; hint?: string }) {
  return (
    <section className="preview">
      <h3>{title}</h3>
      {hint && <p className="muted">{hint}</p>}
      <div className="mock-form">
        {fields.map((f) => (
          <div key={f.field_id} className={`mock-field${"action" in f ? ` mock-${f.action}` : ""}`}>
            <label>
              {f.label}{f.required ? <span className="req" aria-label="required"> *</span> : <span className="muted"> (optional)</span>}
            </label>
            <MockInput f={f} />
            {"microcopy" in f && f.microcopy && <small className="microcopy">{f.microcopy}</small>}
          </div>
        ))}
        {removed.length > 0 && (
          <div className="mock-removed">
            <h4>Removed</h4>
            <ul>
              {removed.map((r) => <li key={r.field_id}><s>{r.label}</s> <small className="muted">— {r.reason}</small></li>)}
            </ul>
          </div>
        )}
        {delayed.length > 0 && (
          <div className="mock-delayed">
            <h4>Collect later</h4>
            <ul>
              {delayed.map((d) => <li key={d.field_id}><b>{d.label}</b> <small className="muted">— {d.note}</small></li>)}
            </ul>
          </div>
        )}
      </div>
    </section>
  );
}
