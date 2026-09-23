import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { api, errorMessage } from "../api";
import { ACTIONS } from "../lib/actions";
import ActionBadge from "./ActionBadge";

type Page = "start" | "review" | "result";

interface Step {
  page: Page;
  /** CSS selector of the element this step talks about. */
  target: string;
  /** Whether the field drawer should be open on the Review page. */
  drawer?: boolean;
  eyebrow: string;
  title: string;
  body: ReactNode;
}

const STEPS: Step[] = [
  {
    page: "start",
    target: ".hero",
    eyebrow: "Less data, less risk",
    title: "Every field you drop is one you never have to defend.",
    body: (
      <ul className="ob-list">
        <li><b>No breach</b> to report, <b>no deletion request</b> to chase</li>
        <li><b>No awkward questions</b> from a regulator</li>
        <li>Shorter forms, <b>smaller risk</b></li>
      </ul>
    ),
  },
  {
    page: "start",
    target: ".start-main",
    eyebrow: "Results in seconds",
    title: "From spreadsheet to privacy review in one drop.",
    body: (
      <>
        <ul className="ob-list">
          <li><b>No setup</b>, no integration, no waiting on legal</li>
          <li>Works with <b>CSV and Excel</b></li>
          <li>Only field definitions go in, <b>never personal data</b></li>        </ul>
        <p className="muted small">Press Next and we'll open a sample for you.</p>
      </>
    ),
  },
  {
    page: "review",
    target: ".legend-wrap",
    eyebrow: "Spot the risk instantly",
    title: "See your whole form's risk at a glance.",
    body: (
      <>
        <ul className="ob-list">
          <li><b>Over-collection and sensitive data</b> jump out in one colour bar</li>
          <li>Every flag backed by <b>the exact legal article</b></li>
        </ul>
        <div className="ob-badges">
          {ACTIONS.map((a) => <ActionBadge key={a} action={a} sm />)}
          <span className="tag tag-ok">Time-limited</span>
        </div>
      </>
    ),
  },
  {
    page: "review",
    target: ".drawer",
    drawer: true,
    eyebrow: "Know every field",
    title: "Click any field for the full picture.",
    body: (
      <ul className="ob-list">
        <li><b>Why</b> it was flagged, and <b>what it costs</b> to ignore</li>
        <li><b>Where it goes</b>: CRM, analytics, third parties</li>
        <li><b>How long</b> you keep it, and when to delete it</li>
      </ul>
    ),
  },
  {
    page: "review",
    target: ".drawer .decide-list",
    drawer: true,
    eyebrow: "Always in control",
    title: "AI speed, with you in charge.",
    body: (
      <ul className="ob-list">
        <li><b>Legal checks</b> the AI can't override</li>
        <li>The AI sees field names, <b>never a single record</b></li>        <li><b>The final call is yours</b>, every exception on record</li>
      </ul>
    ),
  },
  {
    page: "result",
    target: ".export-grid",
    eyebrow: "Ready to ship",
    title: "One click to an audit-ready report.",
    body: (
      <ul className="ob-list">
        <li><b>Product</b> gets a to-do list</li>
        <li><b>Legal</b> gets every decision and the article behind it</li>
        <li><b>Engineering</b> gets the JSON to build from</li>
      </ul>
    ),
  },
];

/** Give up waiting for a page to show its element after this long. */
const WAIT_MS = 20000;
const PAD = 6;

interface Box { top: number; left: number; width: number; height: number }

function pathFor(page: Page, formId: string | null): string | null {
  if (page === "start") return "/";
  return formId ? `/forms/${formId}/${page}` : null;
}

function click(selector: string) {
  document.querySelector<HTMLElement>(selector)?.click();
}

/** How long the highlight takes to glide from one element to the next. */
const GLIDE_MS = 420;

const easeInOut = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2);

/** A box part-way between `a` and `b`: t = 0 is a, t = 1 is b. */
function mix(a: Box, b: Box, t: number): Box {
  const at = (x: number, y: number) => x + (y - x) * t;
  return { top: at(a.top, b.top), left: at(a.left, b.left), width: at(a.width, b.width), height: at(a.height, b.height) };
}

function measure(el: HTMLElement): Box {
  const r = el.getBoundingClientRect();
  return { top: r.top - PAD, left: r.left - PAD, width: r.width + PAD * 2, height: r.height + PAD * 2 };
}

/** Put the card below the highlight, else above, else beside it, else docked at the bottom. */
function placeCard(box: Box | null, cardH: number): { left: number; top: number; width: number } {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const width = Math.min(360, vw - 32);
  const gap = 14;
  if (!box) return { width, left: (vw - width) / 2, top: Math.max(16, (vh - cardH) / 2) };

  const clamp = (n: number, lo: number, hi: number) => Math.max(lo, Math.min(n, hi));
  const left = clamp(box.left + box.width / 2 - width / 2, 16, vw - width - 16);
  const bottom = box.top + box.height;

  if (vh - bottom - gap >= cardH + 16) return { width, left, top: bottom + gap };
  if (box.top - gap >= cardH + 16) return { width, left, top: box.top - gap - cardH };
  if (box.left >= width + gap * 2) return { width, left: box.left - width - gap, top: clamp(box.top + 24, 16, vh - cardH - 16) };
  return { width: vw - 32, left: 16, top: vh - cardH - 16 };
}

export default function Onboarding({ onClose }: { onClose: () => void }) {
  const nav = useNavigate();
  const [i, setI] = useState(0);
  const [formId, setFormId] = useState<string | null>(null);
  const [status, setStatus] = useState<"finding" | "ready" | "lost">("finding");
  const [opening, setOpening] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const cardRef = useRef<HTMLDivElement>(null);
  const spotRef = useRef<HTMLDivElement>(null);
  const blockRef = useRef<HTMLDivElement>(null);
  const primaryRef = useRef<HTMLButtonElement>(null);

  // What the animation loop reads. Refs, not state: changing them must not re-render 60 times a second.
  const target = useRef<HTMLElement | null>(null);
  const shown = useRef<Box | null>(null);
  const glide = useRef<{ from: Box | null; start: number }>({ from: null, start: 0 });

  const step = STEPS[i];
  const last = i === STEPS.length - 1;

  // One loop for the whole tour. Each frame it works out where the highlight should be and
  // writes it straight onto the elements. While a new target loads, the old highlight stays put.
  useLayoutEffect(() => {
    let frame = 0;
    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const tick = () => {
      const el = target.current;
      if (el) {
        const live = measure(el);
        const { from, start } = glide.current;
        const t = still || !from ? 1 : Math.min(1, (performance.now() - start) / GLIDE_MS);
        // Aim at the live position, so the glide lands on the element even while the page scrolls.
        shown.current = t < 1 && from ? mix(from, live, easeInOut(t)) : live;
      }
      const box = shown.current;

      const spot = spotRef.current;
      if (spot) {
        spot.style.display = box ? "block" : "none";
        if (box) Object.assign(spot.style, { top: `${box.top}px`, left: `${box.left}px`, width: `${box.width}px`, height: `${box.height}px` });
      }
      blockRef.current?.classList.toggle("dim", !box);

      const card = cardRef.current;
      if (card) {
        const p = placeCard(box, card.offsetHeight);
        Object.assign(card.style, { top: `${p.top}px`, left: `${p.left}px`, width: `${p.width}px` });
      }
      frame = window.requestAnimationFrame(tick);
    };
    tick();
    return () => window.cancelAnimationFrame(frame);
  }, []);

  // Each step: go to its page, open or close the drawer, wait for the element, then aim at it.
  useEffect(() => {
    const s = STEPS[i];
    let cancelled = false;
    let poll = 0;
    let found: HTMLElement | null = null;
    setStatus("finding");
    target.current = null;

    const path = pathFor(s.page, formId);
    if (path && window.location.pathname !== path) nav(path);

    const started = Date.now();
    function find() {
      if (cancelled) return;
      const drawerOpen = document.querySelector(".drawer") !== null;
      if (s.drawer && !drawerOpen) click(".field-row .f-open");
      if (!s.drawer && drawerOpen) click(".drawer-close");

      const el = document.querySelector<HTMLElement>(s.target);
      if (el && drawerOpen === Boolean(s.drawer)) return follow(el);
      if (Date.now() - started > WAIT_MS) return setStatus("lost");
      poll = window.setTimeout(find, 120);
    }

    function follow(el: HTMLElement) {
      found = el;
      el.classList.add("tour-target");
      if (getComputedStyle(el).position !== "fixed") {
        const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        el.scrollIntoView({ behavior: still ? "auto" : "smooth", block: "start" });
      }
      // Glide from wherever the highlight is now (null on the very first step: just appear).
      glide.current = { from: shown.current, start: performance.now() };
      target.current = el;
      setStatus("ready");
    }

    find();
    return () => {
      cancelled = true;
      window.clearTimeout(poll);
      found?.classList.remove("tour-target");
    };
  }, [i, formId, nav]);

  useEffect(() => { primaryRef.current?.focus(); }, [i, status]);

  function finish() {
    onClose();
    nav("/");
  }

  async function next() {
    if (last) return finish();
    // Leaving the Start page: the next steps need a real form to point at.
    if (STEPS[i + 1].page !== "start" && !formId) {
      setOpening(true);
      setError(null);
      try {
        const demos = await api.demoForms();
        const pick = demos.find((d) => d.cached) ?? demos[0];
        if (!pick) throw new Error("No sample forms available.");
        const form = await api.createDemo(pick.form_id);
        setFormId(form.form_id);
      } catch (e) {
        setError(errorMessage(e));
        setOpening(false);
        return;
      }
      setOpening(false);
    }
    setI(i + 1);
  }

  function back() {
    if (i > 0) setI(i - 1);
  }

  // Re-registered every render so the keys always call the current next/back.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") finish();
      if (e.key === "ArrowRight" && !opening) void next();
      if (e.key === "ArrowLeft") back();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  // Position, size and dimming of these three are set by the animation loop, not by React.
  return (
    <>
      {/* Swallows clicks so the page can't be changed underneath the tour. */}
      <div ref={blockRef} className="tour-block dim" />
      <div ref={spotRef} className="tour-spot" />

      <div ref={cardRef} className="ob" role="dialog" aria-modal="true" aria-labelledby="ob-title">
        <header className="ob-head">
          <span className="eyebrow">{step.eyebrow}</span>
          <span className="grow" />
          <span className="tiny faint">{i + 1} of {STEPS.length}</span>
          <button type="button" className="drawer-close" aria-label="Close tour" onClick={finish}>✕</button>
        </header>

        <div className="ob-body" key={i}>
          <h2 id="ob-title">{step.title}</h2>
          {step.body}
          {status === "finding" && <p className="tiny faint">Loading this part of the app…</p>}
          {status === "lost" && <p className="tiny" style={{ color: "var(--remove)" }}>Couldn't load this part. Is the backend running?</p>}
          {error && <p className="tiny" style={{ color: "var(--remove)" }}>{error}</p>}
        </div>

        <footer className="ob-foot">
          <div className="ob-dots" aria-hidden="true">
            {STEPS.map((_, n) => <i key={n} className={n === i ? "on" : n < i ? "past" : ""} />)}
          </div>
          <span className="grow" />
          {!last && <button type="button" className="quiet sm" onClick={finish}>Skip</button>}
          {i > 0 && <button type="button" className="ghost sm" onClick={back}>Back</button>}
          <button ref={primaryRef} type="button" className="sm" disabled={opening} onClick={() => void next()}>
            {opening ? "Opening a sample…" : last ? "Start with your own form" : "Next"}
          </button>
        </footer>
      </div>
    </>
  );
}
