import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, errorMessage } from "../api";
import SendPanel from "../components/SendPanel";
import { ACTION_SHORT } from "../lib/actions";
import { isLostSession, restore } from "../lib/session";
import type { Action, ApplyResponse } from "../types";

const ORDER: Action[] = ["remove", "make_optional", "better_explain", "keep"];

export default function Result() {
  const { id = "" } = useParams();
  const nav = useNavigate();
  const [data, setData] = useState<ApplyResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api.apply(id)
      .then((d) => !cancelled && setData(d))
      .catch(async (e) => {
        if (cancelled) return;
        if (isLostSession(e)) {
          // Rebuilt sessions have no analysis yet, so hand them back to the decisions step.
          const fresh = await restore(id).catch(() => null);
          if (fresh) { nav(`/forms/${fresh}/review`, { replace: true }); return; }
        }
        setError(errorMessage(e));
      });
    return () => { cancelled = true; };
  }, [id, nav]);

  if (error) {
    return <div className="error" role="alert">{error} <Link to={`/forms/${id}/review`}>Back to the decisions</Link></div>;
  }
  if (!data) return <p className="muted">Applying your decisions…</p>;

  const { report } = data;
  const s = report.summary;
  const deadlines = report.rows.filter((r) => r.delete_by);

  return (
    <>
      <section className="result-hero">
        <div className="seal" aria-hidden="true">✓</div>
        <h1>{report.form.name} is minimised</h1>
        <p className="muted">
          {s.n_fields} fields reviewed, every decision on the record with the article behind it. Hand the report to
          whoever owns this form.
        </p>
      </section>

      <section className="export-block">
        <div className="eb-head">
          <h2>Take it away</h2>
          <p className="muted small">
            The report is the deliverable: every field, every decision, the article behind it, and the
            to-do list for whoever owns this form.
          </p>
        </div>
        <div className="export-grid">
          <a className="export-card primary" href={api.reportUrl(id, "html")} target="_blank" rel="noreferrer">
            <span className="ec-icon" aria-hidden="true">📄</span>
            <span className="ec-body">
              <span className="ec-title">Open the full report</span>
              <span className="ec-sub">Every decision, reason and article, with the actions to take. Print it or save it as PDF.</span>
            </span>
            <span className="ec-go" aria-hidden="true">↗</span>
          </a>
          <a className="export-card" href={api.reportUrl(id, "csv")} download>
            <span className="ec-icon" aria-hidden="true">📊</span>
            <span className="ec-body">
              <span className="ec-title">Download CSV</span>
              <span className="ec-sub">One row per field, deletion deadline included.</span>
            </span>
            <span className="ec-go" aria-hidden="true">↓</span>
          </a>
          <a className="export-card" href={api.reportUrl(id, "json")} download>
            <span className="ec-icon" aria-hidden="true">{"{ }"}</span>
            <span className="ec-body">
              <span className="ec-title">Download JSON</span>
              <span className="ec-sub">The full ruleset, for whoever changes the form in code.</span>
            </span>
            <span className="ec-go" aria-hidden="true">↓</span>
          </a>
        </div>
      </section>

      <SendPanel id={id} report={report} />

      <div className="stats">
        {ORDER.map((a) => (
          <div key={a} className={`stat ${a}`}>
            <div className="n">{s.counts[a] ?? 0}</div>
            <div className="l">{ACTION_SHORT[a]}</div>
          </div>
        ))}
        <div className="stat timed">
          <div className="n">{deadlines.length}</div>
          <div className="l">Time-limited</div>
        </div>
      </div>

      <div className="two-col" style={{ marginTop: "1.5rem" }}>
        <section className="panel">
          <h2>Stop collecting</h2>
          {report.no_longer_collected.length === 0 ? (
            <p className="muted small">Nothing — every field stays in the form.</p>
          ) : (
            <ul className="list-plain">
              {report.no_longer_collected.map((x) => <li key={x}><span>{x}</span></li>)}
            </ul>
          )}
        </section>

        <section className="panel">
          <h2>Has to be deleted by</h2>
          {deadlines.length === 0 ? (
            <p className="muted small">No field carries a deletion deadline. You can set one per field in the previous step.</p>
          ) : (
            <ul className="list-plain">
              {deadlines.map((r) => (
                <li key={r.field_id}>
                  <span>{r.label}</span>
                  <span className="when">{new Date(r.delete_by!).toLocaleDateString(undefined, { day: "numeric", month: "long", year: "numeric" })}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <p className="tiny faint" style={{ marginTop: "1.5rem" }}>
        Generated {new Date(report.generated_at).toLocaleString()} · AI: {report.ai_model ?? "unavailable"}
        {report.cached && " (cached)"} · {s.n_overrides_flagged} decision{s.n_overrides_flagged === 1 ? "" : "s"} flagged below the compliance floor ·{" "}
        <Link to={`/forms/${id}/review`}>Back to the decisions</Link> · <Link to="/">Start over</Link>
      </p>
    </>
  );
}
