import { useEffect, useRef, useState, type DragEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api, errorMessage } from "../api";
import type { DemoFormInfo, HealthResponse } from "../types";

export default function Start() {
  const nav = useNavigate();
  const [demos, setDemos] = useState<DemoFormInfo[]>([]);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [sample, setSample] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<"sample" | "upload" | null>(null);
  const [over, setOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.demoForms().then(setDemos).catch((e) => setError(errorMessage(e)));
    api.health().then(setHealth).catch(() => setHealth(null));
  }, []);

  async function openSample() {
    if (!sample) return;
    setBusy("sample");
    setError(null);
    try {
      const f = await api.createDemo(sample);
      nav(`/forms/${f.form_id}/context`);
    } catch (e) {
      setError(errorMessage(e));
      setBusy(null);
    }
  }

  async function handleFile(file: File | undefined) {
    if (!file) return;
    setBusy("upload");
    setError(null);
    try {
      const forms = await api.upload(file);
      nav(`/forms/${forms[0].form_id}/context`);
    } catch (e) {
      setError(errorMessage(e));
      setBusy(null);
    } finally {
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  function onDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setOver(false);
    if (busy) return;
    void handleFile(e.dataTransfer.files?.[0]);
  }

  const aiReady = Boolean(health?.api_key_set && health?.model);

  return (
    <>
      <section className="hero">
        <span className="eyebrow">GDPR · revFADP</span>
        <h1>Collect only what you actually need.</h1>
        <p>
          Drop in a form and get a decision per field — keep it, explain it, make it optional, delete it after a set
          time, or stop collecting it — each with the reason and the article behind it.
        </p>
      </section>

      {error && <div className="error" role="alert">{error}</div>}

      <div className="start-main">
        <div className="sample-bar">
          <label htmlFor="sample">Just looking?</label>
          <select id="sample" value={sample} onChange={(e) => setSample(e.target.value)} disabled={busy !== null}>
            <option value="">Pick a sample form…</option>
            {demos.map((d) => (
              <option key={d.form_id} value={d.form_id}>
                {d.name} — {d.n_fields} fields{d.cached ? " · instant" : ""}
              </option>
            ))}
          </select>
          <button type="button" className="ghost sm" onClick={() => void openSample()} disabled={!sample || busy !== null}>
            {busy === "sample" ? "Opening…" : "Open"}
          </button>
        </div>

        <div
          className={`dropzone${over ? " over" : ""}${busy === "upload" ? " busy" : ""}`}
          onDragOver={(e) => { e.preventDefault(); setOver(true); }}
          onDragLeave={() => setOver(false)}
          onDrop={onDrop}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".csv,.xlsx"
            aria-label="Upload a form definition"
            disabled={busy !== null}
            onChange={(e) => void handleFile(e.target.files?.[0])}
          />
          <div className="dz-icon" aria-hidden="true">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M10 13V3m0 0L6.5 6.5M10 3l3.5 3.5" />
              <path d="M3 12v3a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-3" />
            </svg>
          </div>
          <div className="dz-title">{busy === "upload" ? "Reading your form…" : "Drop your form definition here"}</div>
          <div className="dz-sub">or click to choose a file · CSV or XLSX</div>
          <div className="dz-hint">
            One row per field: <code>form_id, field_name, field_label, field_type, required, data_category,
            purpose_text, retention_days, system_destination, third_party_shared</code>
          </div>
        </div>

        <p className="tiny faint" style={{ textAlign: "center", marginTop: ".9rem" }}>
          {aiReady ? `Assessment runs on ${health?.model}.` : "AI not configured — you still get the deterministic compliance checks."}
        </p>
      </div>

      <section className="how">
        <div className="how-item">
          <div className="n">1</div>
          <h3>You give the context</h3>
          <p>A few questions about what the form is for and who fills it in. No AI, no data — just the setting.</p>
        </div>
        <div className="how-item">
          <div className="n">2</div>
          <h3>Checks and AI write rules</h3>
          <p>Deterministic legal checks set a floor. The AI judges necessity. Neither ever sees a single record.</p>
        </div>
        <div className="how-item">
          <div className="n">3</div>
          <h3>You decide, we export</h3>
          <p>Every recommendation is yours to accept or overrule, then it leaves as a report for whoever owns the form.</p>
        </div>
      </section>
    </>
  );
}
