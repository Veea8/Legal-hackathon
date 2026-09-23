/* Where forms actually live.
 *
 * Every entry maps to a real form the server can load, so a click always lands on the genuine
 * pipeline — names and field counts are read from /api/demo-forms at render time rather than
 * written down here, which is why there are no dead rows in the list. */

export interface Connector {
  id: string;
  name: string;
  mark: string;
  color: string;
  workspace: string;
  /** form ids as the API reports them */
  formIds: string[];
  /** flavour line per form id — the bit a real workspace listing would show */
  meta: Record<string, string>;
}

export const CONNECTORS: Connector[] = [
  {
    id: "typeform",
    name: "Typeform",
    mark: "T",
    color: "#262627",
    workspace: "Typeform workspace",
    formIds: ["F001"],
    meta: { F001: "Live · 142 responses · edited 2 days ago" },
  },
  {
    id: "google",
    name: "Google Forms",
    mark: "▤",
    color: "#7248b9",
    workspace: "Google Drive",
    formIds: ["F004", "F005"],
    meta: { F004: "Shared with 3 people · 61 responses", F005: "Accepting responses · edited last week" },
  },
  {
    id: "hubspot",
    name: "HubSpot",
    mark: "◉",
    color: "#ff7a59",
    workspace: "HubSpot portal",
    formIds: ["F002"],
    meta: { F002: "Lead capture · embedded on 4 pages" },
  },
  {
    id: "workday",
    name: "Workday",
    mark: "◆",
    color: "#0875e1",
    workspace: "Workday tenant",
    formIds: ["F003"],
    meta: { F003: "HR business process · 61 hires this year" },
  },
];

export const API_TILE = { id: "api", name: "Push it from your own system", mark: "{ }", color: "#12141a" };

export function curlSnippet(origin: string): string {
  return [
    `curl -X POST ${origin}/api/forms \\`,
    `  -H 'Content-Type: application/json' \\`,
    `  -d '{"source":"paste","name":"Signup",`,
    `       "text":"Full name *\\nEmail *\\nDate of birth\\nID document upload"}'`,
  ].join("\n");
}
