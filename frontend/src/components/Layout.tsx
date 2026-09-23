import { Link, NavLink, Outlet, useLocation } from "react-router-dom";

const STEPS = ["Input", "Context", "Review", "Result"];

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
  return (
    <div className="app">
      <header className="topbar">
        <Link to="/" className="brand">
          <span className="brand-mark" aria-hidden="true">◧</span> Data Minimiser
        </Link>
        <nav aria-label="Main">
          <NavLink to="/" end>Start</NavLink>
          <NavLink to="/about">About</NavLink>
        </nav>
      </header>
      {step >= 0 && (
        <ol className="steps" aria-label="Progress">
          {STEPS.map((s, i) => (
            <li key={s} className={i === step ? "active" : i < step ? "done" : ""} aria-current={i === step ? "step" : undefined}>
              <span className="step-num">{i + 1}</span> {s}
            </li>
          ))}
        </ol>
      )}
      <main className="content">
        <Outlet />
      </main>
      <footer className="foot">
        Compliance checks are deterministic. The AI only ever sees field names, labels and purposes, never data values.
        A human decides. Not legal advice.
      </footer>
    </div>
  );
}
