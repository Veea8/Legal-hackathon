import { ACTION_LABEL, MODIFIER_LABEL } from "../lib/actions";
import type { Action, Modifier } from "../types";

export default function ActionBadge({ action, modifiers, small }: { action: Action; modifiers?: Modifier[]; small?: boolean }) {
  return (
    <span className={`badge badge-${action}${small ? " badge-small" : ""}`}>
      {ACTION_LABEL[action]}
      {modifiers && modifiers.length > 0 && (
        <span className="badge-mods"> + {modifiers.map((m) => MODIFIER_LABEL[m]).join(", ")}</span>
      )}
    </span>
  );
}
