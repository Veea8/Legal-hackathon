import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError, api, errorMessage } from "../api";
import ReviewTable from "../components/ReviewTable";
import { formatDate } from "../lib/actions";
import type { CheckResult, FormSchema, KBEntry, RuleOverride, RuleSet } from "../types";

export default function Review() {
  const { id = "" } = useParams();
  const nav = useNavigate();
  const [schema, setSchema] = useState<FormSchema | null>(null);
  const [checks, setChecks] = useState<CheckResult[]>([]);
  const [kb, setKb] = useState<KBEntry[]>([]);
  const [ruleset, setRuleset] = useState<RuleSet | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [rowErrors, setRowErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [runKey, setRunKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.getForm(id), api.checks(id), api.kb()])
      .then(([f, c, k]) => {
        if (cancelled) return;
        setSchema(f);
        setChecks(c);
        setKb(k);
      })
      .catch((e) => !cancelled && setError(errorMessage(e)));
    return () => {
      cancelled = true;
    };
  }, [id]);

  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;
    async function tick() {
      try {
        let rs: RuleSet;
        try {
          rs = await api.analysis(id);
        } catch (e) {
          if (e instanceof ApiError && e.status === 404) rs = await api.analyze(id, false);
          else throw e;
        }
        if (cancelled) return;
        setRuleset(rs);
        if (rs.status === "running") timer = window.setTimeout(() => void tick(), 1000);
      } catch (e) {
        if (!cancelled) setError(errorMessage(e));
      }
    }
    void tick();
    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [id, runKey]);

  const onOverride = useCallback(
    async (o: RuleOverride) => {
      setRowErrors((r) => ({ ...r, [o.field_id]: "" }));
      try {
        const rs = await api.putRules(id, [o]);
        setRuleset(rs);
      } catch (e) {
        setRowErrors((r) => ({ ...r, [o.field_id]: errorMessage(e) }));
      }
    },
    [id],
  );

  async function rerunLive() {
    setBusy(true);
    setError(null);
    try {
      const rs = await api.analyze(id, true);
      setRuleset(rs);
      setRunKey((k) => k + 1);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  async function applyRules() {
    setBusy(true);
    setError(null);
    try {
      await api.apply(id);
      nav(`/forms/${id}/result`);
    } catch (e) {
      setError(errorMessage(e));
      setBusy(false);
    }
  }

  if (!schema) return error ? <div className="error" role="alert">{error}</div> : <p className="muted">Loading…</p>;

  const running = !ruleset || ruleset.status === "running";
  const nErrors = ruleset ? Object.keys(ruleset.ai_errors).length : 0;
  const nDisagree = ruleset ? ruleset.rules.filter((r) => r.disagreement).length : 0;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Review: {schema.name}</h1>
          <p className="muted">{schema.business_context} · {schema.fields.length} fields · <Link to={`/forms/${id}/context`}>edit context</Link></p>
        </div>
        <button type="button" onClick={() => void applyRules()} disabled={busy || running}>
          {busy ? "Applying…" : "Apply rules →"}
        </button>
      </div>

      <div className="status-line" aria-live="polite">
        <span className="tag tag-ok">Checks: done</span>
        <span className={`tag ${running ? "tag-warn" : "tag-ok"}`}>
          AI: {ruleset ? `${ruleset.fields_done}/${ruleset.fields_total}` : "starting"}{running ? " (running…)" : ""}
        </span>
        {ruleset && !running && (
          ruleset.cached ? (
            <span className="tag">
              cached from {formatDate(ruleset.computed_at)} ·{" "}
              <button type="button" className="link" onClick={() => void rerunLive()} disabled={busy}>Re-run live</button>
            </span>
          ) : (
            <span className="tag">live · {ruleset.ai_model ?? "no AI model"}</span>
          )
        )}
        {nErrors > 0 && <span className="tag tag-warn">AI unavailable for {nErrors} field{nErrors === 1 ? "" : "s"}, rule results stand</span>}
        {nDisagree > 0 && <span className="tag tag-warn">{nDisagree} disagreement{nDisagree === 1 ? "" : "s"} to look at</span>}
      </div>
      {error && <div className="error" role="alert">{error}</div>}

      <ReviewTable
        fields={schema.fields}
        checks={checks}
        ruleset={ruleset}
        kb={kb}
        rowErrors={rowErrors}
        disabled={busy || running}
        onOverride={onOverride}
      />

      <p className="muted small">
        Proposed = the stricter of compliance check and AI, unless you decide otherwise. Choosing something milder
        than the compliance floor requires a note and is flagged in the report.
      </p>
    </>
  );
}
