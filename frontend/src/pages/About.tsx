import { useEffect, useState } from "react";
import { api, errorMessage } from "../api";
import type { KBEntry } from "../types";

export default function About() {
  const [kb, setKb] = useState<KBEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.kb().then(setKb).catch((e) => setError(errorMessage(e)));
  }, []);

  const gdpr = kb.filter((e) => e.law === "gdpr");
  const fadp = kb.filter((e) => e.law === "fadp");

  return (
    <>
      <h1>About</h1>
      <section className="panel">
        <h2>Principles</h2>
        <ul className="plain">
          <li><b>Data minimisation by design.</b> Every field needs a purpose. Mandatory is not the default.</li>
          <li><b>Rules, not magic.</b> Compliance checks are deterministic code you can read. They set a floor the proposal never goes below.</li>
          <li><b>AI for judgement, constrained.</b> The AI assesses necessity and proportionality, writes reasons and microcopy, and may only cite the knowledge base below.</li>
          <li><b>Humans decide.</b> Every proposal is reviewable. Decisions below the floor need a note and appear in the report.</li>
          <li><b>Inclusive optional fields are not penalised.</b> Preferred name, pronouns, language, accessibility needs: fine when optional and explained.</li>
        </ul>
      </section>

      <section className="panel">
        <h2>What the AI sees, and what it never sees</h2>
        <div className="two-col">
          <div>
            <h4>Sees</h4>
            <ul className="plain">
              <li>Field names, labels and types</li>
              <li>Stated purposes, retention, destination systems, third-party sharing</li>
              <li>The business context you enter</li>
              <li>The legal knowledge base below</li>
            </ul>
          </div>
          <div>
            <h4>Never sees</h4>
            <ul className="plain">
              <li>Data values of any kind: not one record, not one row</li>
              <li>The compliance check results (the two assessments are independent)</li>
            </ul>
          </div>
        </div>
      </section>

      <section className="panel">
        <h2>Legal knowledge base</h2>
        <p className="muted">
          The EU General Data Protection Regulation (GDPR) and the revised Swiss Federal Act on Data Protection
          (revFADP, in force since 1 September 2023). Summaries are plain-language paraphrases, not the legal text.
        </p>
        {error && <div className="error">{error}</div>}
        <div className="two-col">
          <div>
            <h3>GDPR</h3>
            <dl className="kb-list">
              {gdpr.map((e) => (<div key={e.id}><dt>{e.article} — {e.title}</dt><dd>{e.plain_summary}</dd></div>))}
            </dl>
          </div>
          <div>
            <h3>revFADP</h3>
            <dl className="kb-list">
              {fadp.map((e) => (<div key={e.id}><dt>{e.article} — {e.title}</dt><dd>{e.plain_summary}</dd></div>))}
            </dl>
          </div>
        </div>
      </section>

      <p className="muted small">
        This tool supports privacy-by-design reviews. It is not legal advice and does not replace a review by a qualified professional.
      </p>
    </>
  );
}
