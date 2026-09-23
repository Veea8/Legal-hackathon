/* Session survival.
 *
 * The server keeps sessions in memory in a single process, so a redeploy, a container recycle or a
 * scale-to-zero wake-up loses them and every later call answers "Unknown form '<id>'". The browser
 * still holds everything needed to rebuild one, so it does: the schema goes to localStorage on the
 * way through, and a 404 rebuilds the session from it rather than dead-ending the user.
 *
 * What is lost in a rebuild is the analysis and any decisions already made — for a demo form the
 * cache makes that instant, and it beats a red box. */

import { ApiError, api } from "../api";
import type { FormSchema } from "../types";

const KEY = "minima.sessions";
const KEEP = 6;

interface Saved {
  id: string;
  schema: FormSchema;
  demoFormId?: string;
  at: number;
}

function read(): Saved[] {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as Saved[]) : [];
  } catch {
    return [];
  }
}

function write(rows: Saved[]) {
  try {
    localStorage.setItem(KEY, JSON.stringify(rows.slice(0, KEEP)));
  } catch {
    /* private window, or storage full — recovery is a nicety, never a requirement */
  }
}

export function remember(id: string, schema: FormSchema, demoFormId?: string) {
  const rows = read().filter((r) => r.id !== id);
  const previous = read().find((r) => r.id === id);
  write([{ id, schema, demoFormId: demoFormId ?? previous?.demoFormId, at: Date.now() }, ...rows]);
}

export function recall(id: string): Saved | undefined {
  return read().find((r) => r.id === id);
}

export function forget(id: string) {
  write(read().filter((r) => r.id !== id));
}

/** True when the server has forgotten this session rather than genuinely failing. */
export function isLostSession(e: unknown): boolean {
  return e instanceof ApiError && e.status === 404 && /Unknown form/i.test(e.message);
}

/**
 * Rebuild a forgotten session from what this browser still holds.
 * Returns the new form id, or null when there is nothing to rebuild from.
 */
export async function restore(id: string): Promise<string | null> {
  const saved = recall(id);
  if (!saved) return null;
  const fresh = await api.createFromSchema(saved.schema, saved.demoFormId);
  forget(id);
  remember(fresh.form_id, fresh, saved.demoFormId);
  return fresh.form_id;
}
