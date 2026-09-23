import { useState } from "react";
import { cite, lawUrl } from "../lib/lawLinks";
import type { KBEntry } from "../types";

/** Legal references, spelled out and linked to the actual article text. A chip nobody can read
    — or look up — is not a reference. */
export default function KbChips({ ids, kb, compact, max = 3 }: { ids: string[]; kb: KBEntry[]; compact?: boolean; max?: number }) {
  const [all, setAll] = useState(false);
  const idx = new Map(kb.map((e) => [e.id, e]));
  const known = ids.map((id) => idx.get(id)).filter((e): e is KBEntry => Boolean(e));
  if (known.length === 0) return <p className="muted small">No specific article — the general minimisation principle applies.</p>;

  if (compact) {
    return (
      <span className="kb-inline">
        {known.map((e) => <span key={e.id} title={e.plain_summary}>{e.article}</span>)}
      </span>
    );
  }

  const shown = all ? known : known.slice(0, max);
  return (
    <div className="kb-chips">
      {shown.map((e) => {
        const href = lawUrl(e);
        return (
          <div key={e.id} className={`kb-chip ${e.law}`}>
            <div className="art">
              {href ? (
                <a href={href} target="_blank" rel="noreferrer" title={`Open ${cite(e)} in a new tab`}>
                  {cite(e)} <span aria-hidden="true">↗</span>
                </a>
              ) : cite(e)}
            </div>
            <div className="ttl">{e.title}</div>
            <div className="sum">{e.plain_summary}</div>
          </div>
        );
      })}
      {known.length > max && (
        <button type="button" className="quiet sm" onClick={() => setAll((a) => !a)}>
          {all ? "Show fewer" : `Show ${known.length - max} more article${known.length - max === 1 ? "" : "s"}`}
        </button>
      )}
    </div>
  );
}
