import { useEffect, useState, type ReactNode } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, errorMessage } from "../api";
import { isLostSession, remember, restore } from "../lib/session";
import type { FormSchema, Jurisdiction, LegalBasis, Stage } from "../types";

/* The context step is a conversation, not a form dump: one question at a time, each answered
   question collapses into a line you can click open again. No AI here — just the setting the
   checks and the assessment need. */

const LOST = "This session expired on the server and could not be rebuilt from this browser. Start again from the form.";

const AUDIENCES = ["Customers", "Leads / prospects", "Patients", "Employees", "Job applicants", "Members", "Students", "Suppliers"];

const RECIPIENTS = [
  "Nobody outside our team",
  "Cloud hosting provider",
  "CRM",
  "Email / marketing tool",
  "Payment provider",
  "Analytics",
  "Insurer",
  "Public authority",
];

const RETENTIONS: { days: number | null; title: string; sub: string }[] = [
  { days: 90, title: "3 months", sub: "Short-lived enquiries, leads that go nowhere." },
  { days: 365, title: "1 year", sub: "Campaigns, applications, support history." },
  { days: 1095, title: "3 years", sub: "Typical for contract and customer data." },
  { days: 3650, title: "10 years", sub: "Only where a bookkeeping or statutory duty says so." },
  { days: null, title: "No fixed limit yet", sub: "We will set deadlines per field in the next step." },
];

interface StepDef {
  key: string;
  question: string;
  why: string;
  /** Short answer shown on the collapsed row. */
  answer: (s: FormSchema) => string;
  done: (s: FormSchema) => boolean;
  body: (s: FormSchema, set: (p: Partial<FormSchema>) => void, next: () => void) => ReactNode;
}

function Choice({ active, title, sub, onClick }: { active: boolean; title: string; sub?: string; onClick: () => void }) {
  return (
    <button type="button" className="choice" aria-pressed={active} onClick={onClick}>
      <span className="c-title">{title}</span>
      {sub && <span className="c-sub">{sub}</span>}
    </button>
  );
}

function Chips({ options, isOn, toggle }: { options: string[]; isOn: (o: string) => boolean; toggle: (o: string) => void }) {
  return (
    <div className="chips">
      {options.map((o) => (
        <button key={o} type="button" className="chip-btn" aria-pressed={isOn(o)} onClick={() => toggle(o)}>
          {o}
        </button>
      ))}
    </div>
  );
}

const STEPS: StepDef[] = [
  {
    key: "context",
    question: "What is this form for?",
    why: "A few words are enough. It decides what counts as necessary for every field below.",
    answer: (s) => s.business_context || "—",
    done: (s) => s.business_context.trim().length > 2,
    body: (s, set, next) => (
      <>
        {/* Deliberately a short single-line input: a paragraph here helps nobody, and the box
            used to invite one. */}
        <label className="field short">
          <span>In a few words</span>
          <input
            autoFocus
            maxLength={120}
            value={s.business_context}
            placeholder="e.g. Booking a first physiotherapy appointment"
            onChange={(e) => set({ business_context: e.target.value })}
            onKeyDown={(e) => { if (e.key === "Enter" && s.business_context.trim().length > 2) next(); }}
          />
        </label>
        <div className="wiz-actions">
          <button type="button" onClick={next} disabled={s.business_context.trim().length < 3}>Continue</button>
        </div>
      </>
    ),
  },
  {
    key: "audience",
    question: "Who fills it in?",
    why: "The same field is fine for an employee and a problem for a stranger at first contact.",
    answer: (s) => (s.audience || "—") + (s.involves_minors ? " · includes under-16s" : ""),
    done: (s) => Boolean(s.audience?.trim()),
    body: (s, set, next) => (
      <>
        <Chips options={AUDIENCES} isOn={(o) => s.audience === o} toggle={(o) => set({ audience: o })} />
        <label className="field" style={{ marginTop: ".8rem" }}>
          <span>Or describe them</span>
          <input value={s.audience ?? ""} placeholder="e.g. parents booking for a child" onChange={(e) => set({ audience: e.target.value || null })} />
        </label>
        <h4 style={{ marginTop: "1.1rem" }}>Can anyone under 16 fill this in?</h4>
        <div className="choice-grid two">
          <Choice active={s.involves_minors === true} title="Yes" sub="Extra protection applies (GDPR Art. 8)." onClick={() => set({ involves_minors: true })} />
          <Choice active={s.involves_minors === false} title="No" sub="Adults only." onClick={() => set({ involves_minors: false })} />
        </div>
        <div className="wiz-actions">
          <button type="button" onClick={next} disabled={!s.audience?.trim()}>Continue</button>
        </div>
      </>
    ),
  },
  {
    key: "jurisdiction",
    question: "Which law applies to you?",
    why: "Switzerland and the EU agree on most of this, but not all of it.",
    answer: (s) => ({ both: "EU + Switzerland", eu: "EU (GDPR)", ch: "Switzerland (revFADP)" })[s.jurisdiction],
    done: () => true,
    body: (s, set, next) => (
      <div className="choice-grid">
        {([
          ["both", "Both", "EU General Data Protection Regulation and the revised Swiss FADP."],
          ["eu", "EU only", "GDPR."],
          ["ch", "Switzerland only", "revFADP / nDSG, in force since 1 September 2023."],
        ] as [Jurisdiction, string, string][]).map(([v, t, sub]) => (
          <Choice key={v} active={s.jurisdiction === v} title={t} sub={sub} onClick={() => { set({ jurisdiction: v }); next(); }} />
        ))}
      </div>
    ),
  },
  {
    key: "basis",
    question: "Why are you allowed to collect this?",
    why: "Every processing needs one of these (GDPR Art. 6). Not sure is a valid answer — we then assume the strictest.",
    answer: (s) =>
      s.legal_basis
        ? { consent: "Consent", contract: "Contract", legal_obligation: "Legal obligation", legitimate_interest: "Legitimate interest" }[s.legal_basis]
        : "Not decided yet",
    done: () => true,
    body: (s, set, next) => (
      <div className="choice-grid">
        {([
          ["contract", "We need it to deliver what they asked for", "Contract — the strongest basis for the fields that make the service work."],
          ["consent", "They said yes to it", "Consent — must be freely given, and withdrawable just as easily."],
          ["legal_obligation", "A law requires us to collect it", "Legal obligation — name the law when you claim this."],
          ["legitimate_interest", "We have a business reason that does not override their rights", "Legitimate interest — needs a balancing test on file."],
        ] as [LegalBasis, string, string][]).map(([v, t, sub]) => (
          <Choice key={v} active={s.legal_basis === v} title={t} sub={sub} onClick={() => { set({ legal_basis: v }); next(); }} />
        ))}
        <button type="button" className="quiet" onClick={() => { set({ legal_basis: null }); next(); }}>Not decided yet →</button>
      </div>
    ),
  },
  {
    key: "stage",
    question: "When in the relationship is this asked?",
    why: "First contact is the moment to ask for least. Almost everything can wait.",
    answer: (s) => (s.stage === "entry" ? "At first contact" : "Later, relationship exists"),
    done: () => true,
    body: (s, set, next) => (
      <div className="choice-grid two">
        <Choice active={s.stage === "entry"} title="At first contact" sub="Signup, lead capture, application, onboarding." onClick={() => { set({ stage: "entry" as Stage }); next(); }} />
        <Choice active={s.stage === "later"} title="Later on" sub="The person is already a customer, patient or employee." onClick={() => { set({ stage: "later" as Stage }); next(); }} />
      </div>
    ),
  },
  {
    key: "recipients",
    question: "Who else sees the answers?",
    why: "Recipients have to be named at collection (GDPR Art. 13(1)(e)) — people cannot consent to a surprise.",
    answer: (s) => s.recipients || "Not stated",
    done: (s) => Boolean(s.recipients?.trim()),
    body: (s, set, next) => {
      const picked = (s.recipients ?? "").split(",").map((x) => x.trim()).filter(Boolean);
      const toggle = (o: string) => {
        const has = picked.includes(o);
        const nextPicked = has ? picked.filter((p) => p !== o) : [...picked, o];
        set({ recipients: nextPicked.join(", ") || null });
      };
      return (
        <>
          <Chips options={RECIPIENTS} isOn={(o) => picked.includes(o)} toggle={toggle} />
          <label className="field" style={{ marginTop: ".8rem" }}>
            <span>Anything else, by name</span>
            <input value={s.recipients ?? ""} placeholder="e.g. Stripe, our accountant" onChange={(e) => set({ recipients: e.target.value || null })} />
          </label>
          <div className="wiz-actions">
            <button type="button" onClick={next}>Continue</button>
            <button type="button" className="quiet" onClick={() => { set({ recipients: null }); next(); }}>Skip</button>
          </div>
        </>
      );
    },
  },
  {
    key: "retention",
    question: "How long do you keep the answers?",
    why: "Data may only be kept as long as the purpose needs it (GDPR Art. 5(1)(e)). This becomes the default deletion deadline.",
    answer: (s) =>
      s.retention_default_days ? (RETENTIONS.find((r) => r.days === s.retention_default_days)?.title ?? `${s.retention_default_days} days`) : "No fixed limit yet",
    done: () => true,
    body: (s, set, next) => (
      <div className="choice-grid">
        {RETENTIONS.map((r) => (
          <Choice
            key={String(r.days)}
            active={s.retention_default_days === r.days}
            title={r.title}
            sub={r.sub}
            onClick={() => { set({ retention_default_days: r.days }); next(); }}
          />
        ))}
      </div>
    ),
  },
];

export default function Context() {
  const { id = "" } = useParams();
  const nav = useNavigate();
  const [schema, setSchema] = useState<FormSchema | null>(null);
  const [open, setOpen] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api.getForm(id)
      .then((f) => !cancelled && setSchema(f))
      .catch(async (e) => {
        if (cancelled) return;
        if (isLostSession(e)) {
          const fresh = await restore(id).catch(() => null);
          if (fresh) { nav(`/forms/${fresh}/context`, { replace: true }); return; }
          setError(LOST);
          return;
        }
        setError(errorMessage(e));
      });
    return () => { cancelled = true; };
  }, [id, nav]);

  const set = (p: Partial<FormSchema>) => setSchema((s) => (s ? { ...s, ...p } : s));

  async function run(live: boolean) {
    if (!schema) return;
    setBusy(true);
    setError(null);
    try {
      const saved = await api.updateForm(id, schema);
      remember(id, saved);
      // Straight to the decisions: that page is built to poll and fill in as fields land, so
      // waiting here for the analysis only hid the progress behind a dead button.
      nav(`/forms/${id}/review`, { state: { live } });
    } catch (e) {
      if (isLostSession(e)) {
        const fresh = await restore(id).catch(() => null);
        if (fresh) { nav(`/forms/${fresh}/context`, { replace: true }); setBusy(false); return; }
        setError(LOST);
      } else {
        setError(errorMessage(e));
      }
      setBusy(false);
    }
  }

  if (!schema) return error ? <div className="error" role="alert">{error}</div> : <p className="muted">Loading…</p>;

  const finished = open >= STEPS.length;

  return (
    <div className="wizard">
      <div className="wiz-head">
        <h1>Tell us about {schema.name}</h1>
        <p className="muted small">
          {schema.fields.length} fields loaded. Nothing is sent to the AI yet — these answers decide what counts as
          necessary.
        </p>
        <div className="wiz-progress"><i style={{ width: `${(Math.min(open, STEPS.length) / STEPS.length) * 100}%` }} /></div>
      </div>

      {error && <div className="error" role="alert">{error}</div>}

      <div className="wiz-list">
        {STEPS.map((step, i) => {
          const isOpen = i === open;
          const isDone = i < open || (finished && step.done(schema));
          return (
            <section key={step.key} className={`wiz-card${isOpen ? " current" : ""}${!isOpen && !isDone ? " upcoming" : ""}`}>
              {isOpen ? (
                <div className="wiz-body">
                  <h2 className="wiz-q">{step.question}</h2>
                  <p className="wiz-why">{step.why}</p>
                  {step.body(schema, set, () => setOpen(i + 1))}
                </div>
              ) : isDone ? (
                <button type="button" className="wiz-done-row" onClick={() => setOpen(i)}>
                  <span className="tick" aria-hidden="true">✓</span>
                  <span className="q">{step.question}</span>
                  <span className="a">{step.answer(schema)}</span>
                  <span className="edit">Edit</span>
                </button>
              ) : (
                <div className="wiz-upcoming-row">
                  <span className="tick" aria-hidden="true" />
                  {step.question}
                </div>
              )}
            </section>
          );
        })}
      </div>

      {finished && (
        <section className="panel wiz-review">
          <h2>Ready to assess {schema.fields.length} fields</h2>
          <p className="muted small">
            The compliance checks run on your machine. The AI gets the field names, labels and purposes plus the
            context above — never a single record.
          </p>
          <div className="wiz-actions">
            <button type="button" onClick={() => void run(false)} disabled={busy}>
              {busy ? "Assessing…" : "Assess the fields →"}
            </button>
            <button type="button" className="quiet" onClick={() => void run(true)} disabled={busy}>
              Re-run live, skip cache
            </button>
          </div>
        </section>
      )}
    </div>
  );
}
