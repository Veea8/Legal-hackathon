import { useEffect, useState } from "react";
import { api, errorMessage } from "../api";
import type { DeliveryPreview, DeliveryRecord, Destination, Report } from "../types";

const TILES: { id: Destination; name: string; sub: string; mark: string; color: string }[] = [
  { id: "teams", name: "Microsoft Teams", sub: "Post to a channel", mark: "T", color: "#5059c9" },
  { id: "slack", name: "Slack", sub: "Post to a channel", mark: "#", color: "#4a154b" },
  { id: "webhook", name: "Your own system", sub: "POST the report JSON", mark: "{ }", color: "#12141a" },
  { id: "email", name: "Email the data owner", sub: "The checklist as a message", mark: "✉", color: "#3d4350" },
  { id: "jira", name: "Jira", sub: "One ticket per action", mark: "J", color: "#0052cc" },
  { id: "calendar", name: "Deletion deadlines", sub: "Reminders in your calendar", mark: "◷", color: "#0f766e" },
];

const NAME: Record<Destination, string> = {
  teams: "Teams", slack: "Slack", webhook: "Webhook", email: "Email", jira: "Jira", calendar: "Calendar",
};

export default function SendPanel({ id, report }: { id: string; report: Report }) {
  const [sel, setSel] = useState<Destination | null>(null);
  const [preview, setPreview] = useState<DeliveryPreview | null>(null);
  const [url, setUrl] = useState("");
  const [to, setTo] = useState("");
  const [log, setLog] = useState<DeliveryRecord[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const deadlines = report.rows.filter((r) => r.delete_by).length;

  useEffect(() => {
    api.deliveries(id).then(setLog).catch(() => setLog([]));
  }, [id]);

  useEffect(() => {
    if (!sel) { setPreview(null); return; }
    let cancelled = false;
    const t = window.setTimeout(() => {
      api.previewDelivery(id, { destination: sel, to })
        .then((p) => !cancelled && setPreview(p))
        .catch((e) => !cancelled && setError(errorMessage(e)));
    }, 250);
    return () => { cancelled = true; window.clearTimeout(t); };
  }, [id, sel, to]);

  async function send() {
    if (!sel) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api.sendDelivery(id, { destination: sel, url });
      setLog(res.log);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  async function copyBody() {
    if (!preview) return;
    try {
      await navigator.clipboard.writeText(preview.body);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      setError("Copying needs a secure context (https or localhost). Select the text instead.");
    }
  }

  return (
    <section className="send-block">
      <div className="sb-head">
        <h2>Send it where the work happens</h2>
        <p className="muted small">
          Same report, shaped for the place it lands — the checklist, the deadlines and the flagged decisions,
          nothing invented on the way.
        </p>
      </div>

      <div className="sb-grid">
        {TILES.map((t) => {
          const dead = t.id === "calendar" && deadlines === 0;
          return (
            <button
              key={t.id}
              type="button"
              className={`sb-tile${sel === t.id ? " on" : ""}`}
              disabled={dead}
              aria-pressed={sel === t.id}
              onClick={() => setSel(sel === t.id ? null : t.id)}
            >
              <span className="sb-mark" style={{ background: t.color }} aria-hidden="true">{t.mark}</span>
              <span className="sb-body">
                <span className="sb-name">{t.name}</span>
                <span className="sb-sub">{dead ? "no deletion deadlines set" : t.sub}</span>
              </span>
            </button>
          );
        })}
      </div>

      {error && <div className="error" role="alert">{error}</div>}

      {sel && preview && (
        <div className="sb-detail">
          <div className="sb-left">
            <h3>{preview.title}</h3>
            <p className="small muted">{preview.subtitle}</p>

            {preview.needs_url && (
              <label className="field">
                <span>{preview.url_label}</span>
                <input
                  type="text"
                  value={url}
                  placeholder={preview.url_placeholder ?? ""}
                  onChange={(e) => setUrl(e.target.value)}
                />
              </label>
            )}

            {preview.destination === "email" && (
              <label className="field">
                <span>Who owns this form?</span>
                <input type="text" value={to} placeholder="dpo@yourcompany.example" onChange={(e) => setTo(e.target.value)} />
              </label>
            )}

            <p className="sb-summary">{preview.summary}</p>
            {preview.note && <p className="tiny faint">{preview.note}</p>}

            <div className="sb-actions">
              {preview.sendable && (
                <button type="button" disabled={busy || !url.trim()} onClick={() => void send()}>
                  {busy ? "Sending…" : `Send to ${NAME[preview.destination]}`}
                </button>
              )}
              {preview.destination === "calendar" && preview.link && (
                <a className="button" href={preview.link} download>Download .ics</a>
              )}
              {preview.destination === "email" && preview.link && (
                <a className="button" href={preview.link}>Open in mail app</a>
              )}
              <button type="button" className="ghost" onClick={() => void copyBody()}>
                {copied ? "Copied" : "Copy payload"}
              </button>
            </div>
          </div>

          <div className="sb-right">
            <h4>This is exactly what goes out</h4>
            <pre className="sb-prev">{preview.body}</pre>
          </div>
        </div>
      )}

      <div className="sb-log">
        <h4>Delivery log</h4>
        {log.length === 0 ? (
          <p className="tiny faint">Nothing sent yet.</p>
        ) : (
          <ul className="list-plain">
            {log.map((r) => (
              <li key={r.id}>
                <span>
                  <span className={`sb-dot ${r.ok ? "ok" : "bad"}`} aria-hidden="true" />
                  {" "}{r.ok ? "Sent" : "Failed"} · {NAME[r.destination]} · <span className="mono">{r.target}</span>
                  {r.detail && <span className="faint"> — {r.detail}</span>}
                </span>
                <span className="when">{new Date(r.at).toLocaleTimeString()}</span>
              </li>
            ))}
          </ul>
        )}
        <p className="tiny faint sb-note">Only deliveries that actually left this machine are recorded.</p>
      </div>
    </section>
  );
}
