import { useEffect, useRef, useState } from "react";
import { API_TILE, CONNECTORS, curlSnippet, type Connector } from "../lib/connectors";
import type { DemoFormInfo } from "../types";

interface Props {
  demos: DemoFormInfo[];
  apiKeySet: boolean;
  busy: boolean;
  onOpenForm: (formId: string) => void;
  onPaste: (text: string) => void;
}

export default function ConnectorRow({ demos, apiKeySet, busy, onOpenForm, onPaste }: Props) {
  const [open, setOpen] = useState<string | null>(null);
  const [connecting, setConnecting] = useState(false);
  const [text, setText] = useState("");
  const [copied, setCopied] = useState(false);
  const timer = useRef<number | undefined>(undefined);
  const preRef = useRef<HTMLPreElement>(null);

  useEffect(() => () => window.clearTimeout(timer.current), []);

  function toggle(id: string) {
    if (open === id) {
      setOpen(null);
      return;
    }
    setOpen(id);
    if (id === API_TILE.id) return;
    // A beat of "Connecting…" is the difference between a connector and a second dropdown.
    setConnecting(true);
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setConnecting(false), 420);
  }

  async function copyCurl() {
    const snippet = curlSnippet(window.location.origin);
    try {
      await navigator.clipboard.writeText(snippet);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      // clipboard needs a secure context — localhost is fine, a LAN IP is not. Select it instead.
      const node = preRef.current;
      if (node) {
        const range = document.createRange();
        range.selectNodeContents(node);
        const sel = window.getSelection();
        sel?.removeAllRanges();
        sel?.addRange(range);
      }
    }
  }

  const found = (c: Connector) => c.formIds.map((id) => demos.find((d) => d.form_id === id)).filter(Boolean) as DemoFormInfo[];
  const active = CONNECTORS.find((c) => c.id === open);

  return (
    <div className="connect-row">
      <div className="cr-label"><span>or pull it from where it lives</span></div>

      <div className="cr-tiles">
        {CONNECTORS.map((c) => (
          <button
            key={c.id}
            type="button"
            className="cr-tile"
            aria-expanded={open === c.id}
            disabled={busy || found(c).length === 0}
            onClick={() => toggle(c.id)}
          >
            <span className="cr-mark" style={{ background: c.color }} aria-hidden="true">{c.mark}</span>
            <span>{c.name}</span>
          </button>
        ))}
      </div>

      <button
        type="button"
        className="cr-tile wide"
        aria-expanded={open === API_TILE.id}
        disabled={busy}
        onClick={() => toggle(API_TILE.id)}
      >
        <span className="cr-mark mono" style={{ background: API_TILE.color }} aria-hidden="true">{API_TILE.mark}</span>
        <span>{API_TILE.name}</span>
      </button>

      {active && (
        <div className="cr-panel">
          {connecting ? (
            <p className="cr-found muted">Connecting to {active.name}…</p>
          ) : (
            <>
              <p className="cr-found">
                {found(active).length} form{found(active).length === 1 ? "" : "s"} found in your {active.workspace}
              </p>
              <ul className="cr-list">
                {found(active).map((d) => (
                  <li key={d.form_id} className="cr-item">
                    <span className="cr-item-main">
                      <span className="cr-item-name">{d.name}</span>
                      <span className="cr-item-meta">{active.meta[d.form_id]} · {d.n_fields} fields</span>
                    </span>
                    <button type="button" className="ghost sm" disabled={busy} onClick={() => onOpenForm(d.form_id)}>
                      Review
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}

      {open === API_TILE.id && (
        <div className="cr-panel custom">
          <div className="cr-col">
            <h4>POST it from your own system</h4>
            <pre className="cr-curl" ref={preRef}>{curlSnippet(window.location.origin)}</pre>
            <div className="row">
              <button type="button" className="ghost sm" onClick={() => void copyCurl()}>
                {copied ? "Copied" : "Copy"}
              </button>
              <a className="tiny faint" href="/docs" target="_blank" rel="noreferrer">Full API reference ↗</a>
            </div>
          </div>
          <div className="cr-col">
            <h4>Or paste the field list</h4>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              disabled={busy || !apiKeySet}
              placeholder={"Full name *\nEmail *\nDate of birth\nID document upload"}
              rows={5}
            />
            {apiKeySet ? (
              <button type="button" className="sm" disabled={busy || !text.trim()} onClick={() => onPaste(text)}>
                {busy ? "Reading…" : "Read the fields"}
              </button>
            ) : (
              <p className="tiny faint">Reading a pasted list needs the model. Drop a CSV above instead.</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
