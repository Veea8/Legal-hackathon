import type { Action, Modifier } from "../types";

export const ACTIONS: Action[] = ["keep", "better_explain", "make_optional", "remove"];

export const STRICTNESS: Record<Action, number> = {
  keep: 0,
  better_explain: 1,
  make_optional: 2,
  remove: 3,
};

/** Plain-language names. "better_explain" is never shown as such — people did not know what it meant. */
export const ACTION_LABEL: Record<Action, string> = {
  keep: "Keep as is",
  better_explain: "Explain why you ask",
  make_optional: "Make optional",
  remove: "Do not collect",
};

/** Short form for badges and tables. */
export const ACTION_SHORT: Record<Action, string> = {
  keep: "Keep",
  better_explain: "Explain",
  make_optional: "Optional",
  remove: "Remove",
};

export const ACTION_HELP: Record<Action, string> = {
  keep: "The field stays exactly as it is today.",
  better_explain: "The field stays, but you add one sentence under it saying why you ask and what happens with the answer.",
  make_optional: "You still ask, but people can leave it blank and still use the service.",
  remove: "The field disappears from this form. Nothing is collected here.",
};

export const ACTION_ICON: Record<Action, string> = {
  keep: "✓",
  better_explain: "✎",
  make_optional: "○",
  remove: "✕",
};

export const MODIFIER_LABEL: Record<Modifier, string> = {
  delay: "collect later",
  role_based: "only for the roles that need it",
  conditional_on_purpose: "only once a purpose is documented",
};

export function isMilder(a: Action, b: Action): boolean {
  return STRICTNESS[a] < STRICTNESS[b];
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

/** Deletion deadline shown to the owner: "has to be deleted by 12 March 2027". */
export function deadlineFrom(days: number | null | undefined, from: Date = new Date()): string | null {
  if (days == null || days <= 0) return null;
  const d = new Date(from);
  d.setDate(d.getDate() + days);
  return d.toLocaleDateString(undefined, { day: "numeric", month: "long", year: "numeric" });
}

export function days(n: number | null | undefined): string {
  if (n == null) return "no limit";
  if (n >= 365) {
    const y = n / 365;
    return `${n} days (${Number.isInteger(y) ? y : y.toFixed(1)} years)`;
  }
  return `${n} days`;
}

export const RETENTION_PRESETS: { days: number; label: string }[] = [
  { days: 30, label: "30 days" },
  { days: 90, label: "3 months" },
  { days: 365, label: "1 year" },
  { days: 1095, label: "3 years" },
  { days: 3650, label: "10 years" },
];
