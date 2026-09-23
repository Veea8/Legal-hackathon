import { useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
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
          <span className="brand-mark" aria-hidden="true">◧</span> Minima
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
        Deterministic compliance checks · the AI sees field names, labels and purposes — never data values · a human decides. Not legal advice.
      </footer>

      {tour && <Onboarding onClose={() => setTour(false)} />}
    </div>
  );
}
