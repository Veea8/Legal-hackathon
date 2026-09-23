/* What happens if the recommendation is ignored, and what you get if you follow it.
   Written for a product owner, not a lawyer — but every claim points at the article it comes from.
   Fine tiers: GDPR Art. 83(4) (up to €10 m / 2 % turnover) and Art. 83(5) (up to €20 m / 4 %);
   revFADP Art. 60 ff. (fines up to CHF 250 000 against the responsible natural person). */

import type { Action, CheckResult, FieldRule } from "../types";

export interface Consequence {
  severity: "high" | "medium";
  /** What goes wrong if the field is left as it is. */
  risk: string;
  /** What following the recommendation buys you. */
  benefit: string;
}

const BY_RULE: Record<string, Consequence> = {
  C02: {
    severity: "high",
    risk:
      "Special-category data (health, religion, ethnicity, political opinion, sexual life, biometrics, criminal offences) is prohibited by default under GDPR Art. 9(1). Without a documented Art. 9(2) exception this is unlawful processing, not a paperwork gap — it sits in the higher fine tier of Art. 83(5): up to €20 million or 4 % of worldwide annual turnover. Authorities usually order deletion and stop further processing while they look at it. Swiss law adds a personal fine of up to CHF 250 000 under revFADP Art. 60 ff.",
    benefit:
      "Dropping the field removes the whole Art. 9 problem: no exception to find, no explicit consent to collect and prove, no high-risk data sitting in your systems waiting for a breach.",
  },
  C07: {
    severity: "high",
    risk:
      "An identity-document upload copies a full set of identifiers — name, date of birth, document number, often nationality and a photo — into your storage. Without a documented legal need this fails both necessity (GDPR Art. 5(1)(c)) and lawfulness (Art. 6). A breach here is straight identity theft, so it is the kind of incident that triggers notification to the authority within 72 hours (Art. 33) and to the people affected (Art. 34).",
    benefit:
      "Not holding the document means there is nothing to leak, nothing to notify about, and no retention argument to win. Verify later and only where the law actually requires it.",
  },
  C09: {
    severity: "high",
    risk:
      "Asking for access to behavioural data or a third-party account at first contact bundles a service with processing that the service does not need. Under GDPR Art. 7(4) consent obtained that way is not freely given, so the whole basis for that processing collapses — retroactively, for everyone who signed up.",
    benefit:
      "Asking later, separately, and only when the person sees what it is for makes the consent valid and gives you a much higher acceptance rate than a blocking ask at signup.",
  },
  C04: {
    severity: "medium",
    risk:
      "A mandatory field with no documented purpose cannot be defended under GDPR Art. 5(1)(c) — 'we might need it' is not a purpose. In an audit, a subject access request under Art. 15, or a complaint, you have to state what you use it for and you will not be able to. Mandatory also means you cannot show the collection was necessary for anyone.",
    benefit:
      "Making it optional keeps the data you genuinely need from the people who want to give it, and moves the field out of the necessity argument entirely.",
  },
  C10: {
    severity: "medium",
    risk:
      "Forcing an identity-related answer (gender, title, marital status) excludes people whose reality is not in your dropdown and gives you data you cannot justify under GDPR Art. 5(1)(c). It is the classic complaint that reaches a supervisory authority through an angry customer rather than an audit.",
    benefit:
      "Optional, with inclusive options and a 'prefer not to say', keeps the useful signal, removes the necessity problem, and stops the field from being the reason someone abandons the form.",
  },
  C05: {
    severity: "medium",
    risk:
      "A sensitive field offered without an explanation leaves people guessing what happens with their answer. GDPR Arts. 12–13 require that they are told, in plain language, at the moment of collection. Missing information is one of the most frequently fined failures because it is trivially visible from the outside — a regulator only has to open your form.",
    benefit:
      "One sentence under the field satisfies the transparency duty, and measurably raises completion rates: people answer sensitive questions when they know why they are asked.",
  },
  C06: {
    severity: "medium",
    risk:
      "Data shared with a third party has to be disclosed at collection — the categories of recipients are a mandatory part of GDPR Art. 13(1)(e). Sharing that people did not see coming is exactly what turns one complaint into an investigation of every recipient in your stack.",
    benefit:
      "Naming the recipient and the reason makes the sharing defensible, and forces the useful question of whether that recipient still needs the field at all.",
  },
  C08: {
    severity: "medium",
    risk:
      "Data kept longer than the purpose requires breaches storage limitation (GDPR Art. 5(1)(e), revFADP Art. 6). Long retention has no upside and a real downside: every extra year is more records in the blast radius of a breach and more work for every deletion request under Art. 17.",
    benefit:
      "A deletion deadline turns an open-ended liability into a scheduled job. You can state the period in your privacy notice and prove you hold to it.",
  },
};

/** Fallback when no compliance rule fired and the recommendation comes from the AI alone. */
const BY_ACTION: Record<Action, Consequence> = {
  remove: {
    severity: "high",
    risk:
      "The assessment found no purpose this field is necessary for. Collecting it anyway breaches data minimisation (GDPR Art. 5(1)(c), revFADP Art. 6(2)) and enlarges every breach, every access request and every deletion request you will ever handle.",
    benefit: "Nothing collected is nothing to secure, justify, answer for or delete.",
  },
  make_optional: {
    severity: "medium",
    risk:
      "Making an answer mandatory means you assert it is necessary for every single person who fills the form. If it is not, the requirement itself is the breach of GDPR Art. 5(1)(c) — and people give you wrong data rather than abandon the form, so the field quietly rots too.",
    benefit: "Optional keeps the field for whoever wants to answer and removes the claim you cannot back up.",
  },
  better_explain: {
    severity: "medium",
    risk:
      "Without a stated reason under the field, you are not meeting the transparency duty of GDPR Arts. 12–13, and people cannot give informed consent to something they do not understand.",
    benefit: "One plain sentence discharges the duty and raises completion — this is the cheapest fix on the page.",
  },
  keep: {
    severity: "medium",
    risk: "No issue found. The field has a purpose it is necessary for, and it is proportionate to that purpose.",
    benefit: "Keep it, and keep the purpose documented so this stays true at the next review.",
  },
};

export function consequenceFor(rule: FieldRule | undefined, check: CheckResult | undefined): Consequence {
  const triggered = (check?.triggered ?? []).filter((t) => t.severity !== "info");
  const blocking = triggered.find((t) => t.severity === "block");
  const hit = (blocking ?? triggered[0])?.rule_id;
  if (hit && BY_RULE[hit]) return BY_RULE[hit];
  return BY_ACTION[rule?.action ?? "keep"];
}

/** One-line hint on a row, so people see the stake before opening anything. */
export function stakeLine(rule: FieldRule | undefined, check: CheckResult | undefined): string | null {
  const blocking = (check?.triggered ?? []).some((t) => t.severity === "block");
  if (blocking) return "Higher fine tier";
  if (rule?.disagreement) return "Checks and AI disagree";
  if (rule?.ai?.special_category) return "Special category";
  return null;
}
