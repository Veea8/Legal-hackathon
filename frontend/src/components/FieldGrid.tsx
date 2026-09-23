import type { FieldSpec, FieldType } from "../types";

const TYPES: FieldType[] = ["text", "textarea", "email", "number", "date", "dropdown", "file", "oauth", "checkbox", "other"];
const CATEGORIES = [
  "personal", "health", "special_category", "special_category_adjacent", "financial", "business_financial",
  "identity", "behavioral", "biometric_adjacent", "criminal_offence", "personal_family", "preferences", "business",
];

function slug(s: string): string {
  return s.trim().toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "") || "field";
}

export default function FieldGrid({ fields, onChange }: { fields: FieldSpec[]; onChange: (fields: FieldSpec[]) => void }) {
  function update(i: number, patch: Partial<FieldSpec>) {
    onChange(fields.map((f, j) => (j === i ? { ...f, ...patch } : f)));
  }
  function remove(i: number) {
    onChange(fields.filter((_, j) => j !== i));
  }
  function add() {
    const n = fields.length + 1;
    onChange([
      ...fields,
      {
        field_id: `new_field_${n}`, order: n, name: `new_field_${n}`, label: "", type: "text", required: false,
        data_category: null, sensitive: null, purpose_text: null, retention_days: null, destination: null,
        third_party_shared: null, options: null, inclusivity_note: null,
      },
    ]);
  }

  return (
    <div className="grid-wrap">
      <datalist id="category-list">
        {CATEGORIES.map((c) => <option key={c} value={c} />)}
      </datalist>
      <table className="grid">
        <thead>
          <tr>
            <th>Label</th><th>Name</th><th>Type</th><th>Required</th><th>Category</th>
            <th>Purpose (why is it collected?)</th><th>Retention (days)</th><th>Destination</th><th>3rd party</th><th></th>
          </tr>
        </thead>
        <tbody>
          {fields.map((f, i) => (
            <tr key={f.field_id + i}>
              <td><input aria-label={`Label of field ${i + 1}`} value={f.label} onChange={(e) => update(i, { label: e.target.value })} /></td>
              <td>
                <input aria-label={`Name of field ${i + 1}`} value={f.name} className="mono"
                  onChange={(e) => update(i, { name: e.target.value, field_id: slug(e.target.value) })} />
              </td>
              <td>
                <select aria-label={`Type of field ${i + 1}`} value={f.type} onChange={(e) => update(i, { type: e.target.value as FieldType })}>
                  {TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
              </td>
              <td className="center">
                <input type="checkbox" aria-label={`Field ${i + 1} required`} checked={f.required} onChange={(e) => update(i, { required: e.target.checked })} />
              </td>
              <td>
                <input aria-label={`Category of field ${i + 1}`} list="category-list" value={f.data_category ?? ""}
                  onChange={(e) => update(i, { data_category: e.target.value || null })} />
              </td>
              <td>
                <input aria-label={`Purpose of field ${i + 1}`} className="wide" value={f.purpose_text ?? ""}
                  placeholder="no purpose stated" onChange={(e) => update(i, { purpose_text: e.target.value || null })} />
              </td>
              <td>
                <input aria-label={`Retention days of field ${i + 1}`} type="number" min={0} className="narrow" value={f.retention_days ?? ""}
                  onChange={(e) => update(i, { retention_days: e.target.value === "" ? null : Number(e.target.value) })} />
              </td>
              <td>
                <input aria-label={`Destination of field ${i + 1}`} className="narrow" value={f.destination ?? ""}
                  onChange={(e) => update(i, { destination: e.target.value || null })} />
              </td>
              <td className="center">
                <input type="checkbox" aria-label={`Field ${i + 1} shared with third party`} checked={!!f.third_party_shared}
                  onChange={(e) => update(i, { third_party_shared: e.target.checked })} />
              </td>
              <td><button type="button" className="link danger" onClick={() => remove(i)} aria-label={`Delete field ${i + 1}`}>✕</button></td>
            </tr>
          ))}
        </tbody>
      </table>
      <button type="button" className="secondary" onClick={add}>+ Add field</button>
    </div>
  );
}
