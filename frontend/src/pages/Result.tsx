import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, errorMessage } from "../api";
import DataFlowMap from "../components/DataFlowMap";
import FormPreview from "../components/FormPreview";
import ReportTable from "../components/ReportTable";
import { ACTION_LABEL, days } from "../lib/actions";
import type { ApplyResponse, FormSchema } from "../types";

export default function Result() {
  const { id = "" } = useParams();
  const [schema, setSchema] = useState<FormSchema | null>(null);
  const [data, setData] = useState<ApplyResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.getForm(id), api.apply(id)])
      .then(([s, d]) => {
        if (cancelled) return;
        setSchema(s);
        setData(d);
      })
      .catch((e) => !cancelled && setError(errorMessage(e)));
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (error) return <div className="error" role="alert">{error} <Link to={`/forms/${id}/review`}>Back to review</Link></div>;
  if (!schema || !data) return <p className="muted">Applying rules…</p>;

  const { minimised, report } = data;
  const s = report.summary;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Result: {schema.name}</h1>
          <p className="muted">
            {s.n_fields} fields · {Object.entries(s.counts).map(([k, v]) => `${ACTION_LABEL[k as keyof typeof ACTION_LABEL] ?? k}: ${v}`).join(" · ")}
            {" · "}special-category: {s.n_special_category} · flagged decisions: {s.n_overrides_flagged}
            {report.cached && " · AI result cached"}
          </p>
        </div>
        <div className="row-actions">
          <a className="button secondary" href={api.reportUrl(id, "csv")} download>Download CSV</a>
          <a className="button secondary" href={api.reportUrl(id, "json")} download>Download JSON</a>
          <a className="button" href={api.reportUrl(id, "html")} target="_blank" rel="noreferrer">Printable report</a>
        </div>
      </div>

      <div className="two-col">
        <FormPreview title="Before" fields={schema.fields} hint="As currently collected." />
        <FormPreview
          title="After"
          fields={minimised.fields}
          removed={minimised.removed}
          delayed={minimised.delayed}
          hint="Minimised form with explanations under the fields."
        />
      </div>

      <div className="two-col">
        <section className="panel">
          <h2>Fields no longer collected here</h2>
          {report.no_longer_collected.length === 0 ? (
            <p className="muted">None. All fields stay in the form.</p>
          ) : (
            <ul>{report.no_longer_collected.map((x) => <li key={x}>{x}</li>)}</ul>
          )}
          <p className="muted small">Hand this list to whoever owns data collection so these fields stop being collected.</p>
        </section>
        <section className="panel">
          <h2>Retention</h2>
          {report.retention_table.length === 0 ? (
            <p className="muted">No retention changes suggested.</p>
          ) : (
            <table className="compact">
              <thead><tr><th>Field</th><th>Current</th><th>Suggested</th></tr></thead>
              <tbody>
                {report.retention_table.map((r) => (
                  <tr key={r.field_id}><td>{r.label}</td><td>{days(r.current_days)}</td><td>{days(r.suggested_days)}</td></tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      </div>

      <h2>Report</h2>
      <ReportTable rows={report.rows} />

      <h2>Where the data goes</h2>
      <DataFlowMap schema={schema} rows={report.rows} />

      <p className="muted small">
        Generated {new Date(report.generated_at).toLocaleString()} · AI: {report.ai_model ?? "unavailable"} ·{" "}
        <Link to={`/forms/${id}/review`}>Back to review</Link> · <Link to="/">Start over</Link>
      </p>
    </>
  );
}
