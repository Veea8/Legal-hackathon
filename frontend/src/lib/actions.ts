import type { Action, Modifier } from "../types";

export const ACTIONS: Action[] = ["keep", "better_explain", "make_optional", "remove"];

export const STRICTNESS: Record<Action, number> = {
  keep: 0,
  better_explain: 1,
  make_optional: 2,
  remove: 3,
};

export const ACTION_LABEL: Record<Action, string> = {
  keep: "Keep",
  better_explain: "Better explain",
  make_optional: "Make optional",
  remove: "Remove",
};

export const MODIFIER_LABEL: Record<Modifier, string> = {
  delay: "collect later",
  role_based: "role-based",
  conditional_on_purpose: "if purpose documented",
};

export function isMilder(a: Action, b: Action): boolean {
  return STRICTNESS[a] < STRICTNESS[b];
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}

export function days(n: number | null | undefined): string {
  if (n == null) return "–";
  return n >= 365 ? `${n} d (${(n / 365).toFixed(1)} y)` : `${n} d`;
}
