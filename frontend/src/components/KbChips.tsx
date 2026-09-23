import type { KBEntry } from "../types";

export default function KbChips({ ids, kb, withSummaries }: { ids: string[]; kb: KBEntry[]; withSummaries?: boolean }) {
  const idx = new Map(kb.map((e) => [e.id, e]));
  if (ids.length === 0) return <span className="muted">none</span>;
  return (
    <div className="kb-chips">
      {ids.map((id) => {
        const e = idx.get(id);
        return (
          <span key={id} className={`chip chip-${e?.law ?? "unknown"}`} title={e ? `${e.article}: ${e.plain_summary}` : id}>
            {e ? `${e.article} · ${e.title}` : id}
            {withSummaries && e && <small className="chip-summary">{e.plain_summary}</small>}
          </span>
        );
      })}
    </div>
  );
}
