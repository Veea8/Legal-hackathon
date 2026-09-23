import { useEffect, useState, type ChangeEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api, errorMessage } from "../api";
import type { DemoFormInfo, HealthResponse } from "../types";

export default function Start() {
  const nav = useNavigate();
  const [demos, setDemos] = useState<DemoFormInfo[] | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [pasteText, setPasteText] = useState("");
  const [pasteName, setPasteName] = useState("");
  const [pasteCtx, setPasteCtx] = useState("");

  useEffect(() => {
    api.demoForms().then(setDemos).catch((e) => setError(errorMessage(e)));
    api.health().then(setHealth).catch(() => setHealth(null));
  }, []);

  async function openDemo(formId: string) {
    setBusy(formId);
    setError(null);
    try {
      const f = await api.createDemo(formId);
      nav(`/forms/${f.form_id}/context`);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(null);
    }
  }

  async function onUpload(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy("upload");
    setError(null);
    try {
      const forms = await api.upload(file);
      nav(`/forms/${forms[0].form_id}/context`);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(null);
      e.target.value = "";
    }
  }

  async function onPaste() {
    setBusy("paste");
    setError(null);
    try {
      const f = await api.createPaste(pasteText, pasteName || undefined, pasteCtx || undefined);
      nav(`/forms/${f.form_id}/context`);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(null);
    }
  }

  return (
    <>
      <section className="hero">
        <h1>Review a form. Collect only what you need.</h1>
        <p>
          Pick a sample form, upload your own field list, or paste one. Deterministic compliance checks and an AI
          assessment propose an action per field — <b>keep</b>, <b>make optional</b>, <b>remove</b> or{" "}
          <b>better explain</b> — with reasons and legal references. You decide; the engine applies.
        </p>
        {health && (
          <p className="muted small">
            AI: {health.api_key_set && health.model ? `${health.model}` : "not configured — compliance checks only"}
            {health.cached_forms.length > 0 && ` · cached demo results: ${health.cached_forms.join(", ")}`}
          </p>
        )}
      </section>

      {error && <div className="error" role="alert">{error}</div>}

      <h2>Sample forms</h2>
      {demos === null ? (
        <p className="muted">Loading…</p>
      ) : (
        <div className="cards">
          {demos.map((d) => (
            <article key={d.form_id} className="card">
              <h3>{d.name}</h3>
              <p className="muted">{d.business_context}</p>
              <p className="small">
                {d.n_fields} fields {d.cached && <span className="tag">cached AI result</span>}
              </p>
              <button type="button" onClick={() => void openDemo(d.form_id)} disabled={busy !== null}>
                {busy === d.form_id ? "Opening…" : "Review this form"}
              </button>
            </article>
          ))}
        </div>
      )}

      <div className="two-col">
        <section className="panel">
          <h2>Upload your own</h2>
          <p className="muted">
            CSV or XLSX in the challenge column format (<code>form_id, field_name, field_label, field_type, required,
            data_category, purpose_text, retention_days, system_destination, third_party_shared …</code>).
          </p>
          <label className="file-label">
            <input type="file" accept=".csv,.xlsx" onChange={(e) => void onUpload(e)} disabled={busy !== null} />
          </label>
        </section>
        <section className="panel">
          <h2>Paste a field list</h2>
          <p className="muted">One field per line, or an HTML form. The AI turns it into a schema you confirm next.</p>
          <label>
            Form name
            <input value={pasteName} onChange={(e) => setPasteName(e.target.value)} placeholder="e.g. Newsletter signup" />
          </label>
          <label>
            Business context
            <input value={pasteCtx} onChange={(e) => setPasteCtx(e.target.value)} placeholder="e.g. B2C marketing" />
          </label>
          <label>
            Fields
            <textarea rows={5} value={pasteText} onChange={(e) => setPasteText(e.target.value)}
              placeholder={"Full name *\nEmail *\nDate of birth\nReligion"} />
          </label>
          <button type="button" onClick={() => void onPaste()} disabled={busy !== null || !pasteText.trim()}>
            {busy === "paste" ? "Extracting…" : "Extract fields"}
          </button>
        </section>
      </div>

      <section className="how">
        <h2>How it works</h2>
        <ol className="how-steps">
          <li><b>Checks + AI write rules.</b> Compliance checks encode legal invariants. The AI judges necessity and proportionality. Both see only field names, labels and purposes.</li>
          <li><b>You decide.</b> Every proposal is reviewable. Going below the compliance floor needs a note and is flagged in the report.</li>
          <li><b>The engine applies.</b> A deterministic engine produces the minimised form, a before/after view and a report for the data owner.</li>
          <li><b>The AI never sees data values.</b> Not one record. Only the schema.</li>
        </ol>
      </section>
    </>
  );
}
