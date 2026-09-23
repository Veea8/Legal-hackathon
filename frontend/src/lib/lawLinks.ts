import type { KBEntry } from "../types";

/* A legal reference nobody can look up is decoration. Every article gets a real URL:
   GDPR -> gdpr-info.eu (article pages), revFADP -> Fedlex SR 235.1, the official English text. */

export const FEDLEX = "https://www.fedlex.admin.ch/eli/cc/2022/491/en";

/** "Art. 5(1)(b)" -> 5 · "Art. 6(6)–(7) revFADP" -> 6 · "Art. 5 let. c revFADP" -> 5 */
export function articleNumber(article: string): number | null {
  const m = article.match(/(\d+)/);
  return m ? Number(m[1]) : null;
}

export function lawUrl(entry: KBEntry): string | null {
  const n = articleNumber(entry.article);
  if (n == null) return null;
  return entry.law === "gdpr" ? `https://gdpr-info.eu/art-${n}-gdpr/` : `${FEDLEX}#art_${n}`;
}

/** FADP entries already carry "revFADP" inside the article string; do not say it twice. */
export function cite(entry: KBEntry): string {
  return entry.law === "gdpr"
    ? `GDPR ${entry.article}`
    : `revFADP ${entry.article.replace(/\s*revFADP\s*/gi, " ").trim()}`;
}
