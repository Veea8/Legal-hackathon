import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, errorMessage } from "../api";
import FieldGrid from "../components/FieldGrid";
import type { FormSchema, Jurisdiction, LegalBasis, Stage } from "../types";

export default function Context() {
  const { id = "" } = useParams();
  const nav = useNavigate();
  const [schema, setSchema] = useState<FormSchema | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.getForm(id).then(setSchema).catch((e) => setError(errorMessage(e)));
  }, [id]);

  function patch(p: Partial<FormSchema>) {
    setSchema((s) => (s ? { ...s, ...p } : s));
  }

  async function saveAndRun(live: boolean) {
    if (!schema) return;
    setBusy(true);
    setError(null);
    try {
      await api.updateForm(id, schema);
      await api.analyze(id, live);
      nav(`/forms/${id}/review`);
    } catch (e) {
      setError(errorMessage(e));
      setBusy(false);
    }
  }

  if (error && !schema) return <div className="error" role="alert">{error}</div>;
  if (!schema) return <p className="muted">Loading…</p>;

  const missingPurpose = schema.fields.filter((f) => !f.purpose_text?.trim()).length;

  return (
    <>
      <h1>Context</h1>
      <p className="muted">
        No AI here. Tell us what the form is for and, per field, why it is collected. A missing purpose is not a
        blocker — it simply leads to a stricter rule and a note in the report.
      </p>
      {error && <div className="error" role="alert">{error}</div>}

      <section className="panel">
        <div className="form-grid">
          <label>Form name<input value={schema.name} onChange={(e) => patch({ name: e.target.value })} /></label>
          <label>Business context<input value={schema.business_context} onChange={(e) => patch({ business_context: e.target.value })} /></label>
          <label>Who fills it in?<input value={schema.audience ?? ""} placeholder="e.g. patients, leads, employees" onChange={(e) => patch({ audience: e.target.value || null })} /></label>
          <label>
            Jurisdiction
            <select value={schema.jurisdiction} onChange={(e) => patch({ jurisdiction: e.target.value as Jurisdiction })}>
              <option value="both">EU (GDPR) + Switzerland (revFADP)</option>
              <option value="eu">EU (GDPR)</option>
              <option value="ch">Switzerland (revFADP)</option>
            </select>
          </label>
          <label>
            Legal basis
            <select value={schema.legal_basis ?? ""} onChange={(e) => patch({ legal_basis: (e.target.value || null) as LegalBasis | null })}>
              <option value="">not specified</option>
              <option value="consent">consent</option>
              <option value="contract">contract</option>
              <option value="legal_obligation">legal obligation</option>
              <option value="legitimate_interest">legitimate interest</option>
            </select>
          </label>
          <label>
            Stage
            <select value={schema.stage} onChange={(e) => patch({ stage: e.target.value as Stage })}>
              <option value="entry">entry (signup, lead, application)</option>
              <option value="later">later (established relationship)</option>
            </select>
          </label>
        </div>
      </section>

      <h2>Fields <small className="muted">({schema.fields.length}; {missingPurpose} without a stated purpose)</small></h2>
      <FieldGrid fields={schema.fields} onChange={(fields) => patch({ fields })} />

      <div className="actions">
        <button type="button" onClick={() => void saveAndRun(false)} disabled={busy || schema.fields.length === 0}>
          {busy ? "Running…" : "Save & run analysis"}
        </button>
        <button type="button" className="secondary" onClick={() => void saveAndRun(true)} disabled={busy || schema.fields.length === 0}>
          Save & run live (skip cache)
        </button>
        <span className="muted small">Cached AI results are used for unchanged sample forms; edited forms always run live.</span>
      </div>
    </>
  );
}
