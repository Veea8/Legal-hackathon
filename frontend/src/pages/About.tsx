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
      <section className="hero" style={{ textAlign: "left", margin: "0 0 2rem" }}>
        <h1>How it works</h1>
        <p>An AI writes rules. It never touches your data. A deterministic engine applies them. You decide everything in between.</p>
      </section>

      <div className="how" style={{ margin: "0 0 2rem", maxWidth: "none" }}>
        <div className="how-item">
          <div className="n">1</div>
          <h3>Checks set the floor</h3>
          <p>Eleven deterministic checks encode the invariants: special categories, mandatory fields without a purpose,
            undisclosed sharing, identity documents, retention. They are plain code, not a prompt.</p>
        </div>
        <div className="how-item">
          <div className="n">2</div>
          <h3>The AI judges necessity</h3>
          <p>Separately, and without seeing the check results, the assessment weighs each field against the purpose and
            its siblings. When it is milder than the floor, the floor wins and the disagreement is surfaced to you.</p>
        </div>
        <div className="how-item">
          <div className="n">3</div>
          <h3>The engine applies</h3>
          <p>Your decisions go through deterministic code — remove, make optional, attach the explanation, set the
            deletion deadline — and out as a report. Same input, same output, every time.</p>
        </div>
      </div>

      <section className="panel">
        <h2>What the AI sees, and what it never sees</h2>
        <div className="two-col" style={{ marginTop: ".75rem" }}>
          <div>
            <h4>Sees</h4>
            <ul className="plain">
              <li>Field names, labels and types</li>
              <li>Stated purposes, retention, destinations, third-party sharing</li>
              <li>The context you entered</li>
              <li>The knowledge base below — and it may cite nothing else</li>
            </ul>
          </div>
          <div>
            <h4>Never sees</h4>
            <ul className="plain">
              <li>Data values of any kind. Not one record, not one row.</li>
              <li>The compliance check results — the two assessments stay independent on purpose</li>
            </ul>
          </div>
        </div>
      </section>

      <section className="panel">
        <h2>Legal knowledge base</h2>
        <p className="muted small">
          The EU General Data Protection Regulation and the revised Swiss Federal Act on Data Protection (revFADP,
          in force since 1 September 2023). Summaries are plain-language paraphrases, not the legal text.
        </p>
        {error && <div className="error">{error}</div>}
        <div className="kb-grid" style={{ marginTop: "1rem" }}>
          <div>
            <h4>GDPR</h4>
            <dl style={{ margin: 0 }}>
              {gdpr.map((e) => (
                <div key={e.id} className="kb-entry">
                  <dt>{e.article} — {e.title}</dt>
                  <dd>{e.plain_summary}</dd>
                </div>
              ))}
            </dl>
          </div>
          <div>
            <h4>revFADP</h4>
            <dl style={{ margin: 0 }}>
              {fadp.map((e) => (
                <div key={e.id} className="kb-entry">
                  <dt>{e.article} — {e.title}</dt>
                  <dd>{e.plain_summary}</dd>
                </div>
              ))}
            </dl>
          </div>
        </div>
      </section>

      <p className="tiny faint" style={{ marginTop: "1.5rem" }}>
        This tool supports privacy-by-design reviews. It is not legal advice and does not replace a review by a qualified professional.
      </p>
    </>
  );
}
