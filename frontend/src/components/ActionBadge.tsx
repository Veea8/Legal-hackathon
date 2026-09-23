import { ACTION_ICON, ACTION_SHORT, MODIFIER_LABEL } from "../lib/actions";
import type { Action, Modifier } from "../types";

export default function ActionBadge({ action, modifiers, sm }: { action: Action; modifiers?: Modifier[]; sm?: boolean }) {
  return (
    <span className={`badge badge-${action}${sm ? " sm" : ""}`}>
      <span aria-hidden="true">{ACTION_ICON[action]}</span>
      {ACTION_SHORT[action]}
      {modifiers && modifiers.length > 0 && (
        <span className="badge-mods">· {modifiers.map((m) => MODIFIER_LABEL[m]).join(", ")}</span>
      )}
    </span>
  );
}
