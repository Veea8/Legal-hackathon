import { useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { FEDLEX } from "../lib/lawLinks";
import Onboarding from "./Onboarding";

const STEPS = ["Form", "Context", "Decisions", "Export"];

function currentStep(pathname: string): number {
  if (pathname === "/") return 0;
  if (pathname.endsWith("/context")) return 1;
  if (pathname.endsWith("/review")) return 2;
  if (pathname.endsWith("/result")) return 3;
  return -1;
}

export default function Layout() {
  const { pathname } = useLocation();
  const step = currentStep(pathname);
  const wide = pathname.endsWith("/review") || pathname.endsWith("/result") || pathname === "/about";
  // Opens on every page load: first visit and every refresh.
  const [tour, setTour] = useState(true);

  return (
    <div className="app">
      <header className="topbar">
        <Link to="/" className="brand">
          <span className="brand-mark" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="currentColor">
              <rect x="5" y="6.4" width="14" height="2.7" rx="1.35" />
              <rect x="5" y="10.65" width="9.5" height="2.7" rx="1.35" />
              <rect x="5" y="14.9" width="5" height="2.7" rx="1.35" />
            </svg>
          </span>
          minima
        </Link>

        {step >= 0 && (
          <ol className="stepper" aria-label="Progress">
            {STEPS.map((s, i) => (
              <li key={s} className={i === step ? "active" : i < step ? "done" : ""}>
                <span className="dot" aria-current={i === step ? "step" : undefined}>
                  <b>{i < step ? "✓" : i + 1}</b> <span>{s}</span>
                </span>
                {i < STEPS.length - 1 && <i className="bar" aria-hidden="true" />}
              </li>
            ))}
          </ol>
        )}

        <nav className="topnav" aria-label="Main">
          <NavLink to="/" end>New form</NavLink>
          <NavLink to="/about">How it works</NavLink>
          <button type="button" className="navlink" onClick={() => setTour(true)}>Tour</button>
        </nav>
      </header>

      <main className={wide ? "content" : "content narrow"}>
        <Outlet />
      </main>

      <footer className="foot">
        <div className="foot-grid">
          <section>
            <h5>
              <span className="flags" aria-hidden="true">🇨🇭 🇪🇺</span> Grounded in the law
            </h5>
            <p>
              Every recommendation cites the article it comes from —{" "}
              <a href={FEDLEX} target="_blank" rel="noreferrer">revFADP</a> Art. 6(2) proportionality,
              6(3) recognisable purpose, 6(4) deletion, 7 privacy by design, 19 duty to inform ·{" "}
              <a href="https://gdpr-info.eu/art-5-gdpr/" target="_blank" rel="noreferrer">GDPR</a> Art. 5(1)(c)
              minimisation, 5(1)(e) storage limitation, 13 transparency, 25 by design and by default.
            </p>
          </section>

          <section>
            <h5>
              <span className="flags" aria-hidden="true">🇨🇭</span> Sovereign, ethical AI
            </h5>
            <p>
              Assessments run on <a href="https://www.swiss-ai.org/apertus" target="_blank" rel="noreferrer">Apertus 70B</a>,
              the open-weight Swiss model, hosted in Switzerland. No US cloud, no training on your forms — and the
              model only ever sees field names, labels and purposes, never a data value.
            </p>
          </section>

          <section>
            <h5>Deterministic first, human last</h5>
            <p>
              Rule checks decide; the model may only add context. Each decision, its legal basis and its deletion date
              leave an exportable audit trail, so the data protection representative can show why every field survived.
            </p>
          </section>
        </div>

        <p className="foot-fine">minima · built at the Legal Hackathon 2026 · not legal advice</p>
      </footer>

      {tour && <Onboarding onClose={() => setTour(false)} />}
    </div>
  );
}
