"""Score our proposals against the jury labels in the challenge workbook. Run from backend/:

    ./.venv/bin/python scripts/eval.py --checks-only     # offline, deterministic floor only
    ./.venv/bin/python scripts/eval.py --cached          # RuleSets from app/cache (falls back to checks-only per missing form)
    ./.venv/bin/python scripts/eval.py --live            # calls Apertus

Metrics: flag accuracy (jury flag Y <=> our action != keep), primary exact (our action == first jury label),
lenient ({action, alternative} intersects the jury's acceptable set), delay-modifier hits.
Writes eval/results-<timestamp>.md (gitignored) and prints every mismatch with our reason vs the jury's.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.checks.rules import run_checks  # noqa: E402
from app.loaders.xlsx import JuryLabel, load_workbook  # noqa: E402
from app.merge import build_ruleset  # noqa: E402
from app.models import Action, FormSchema, Modifier, RuleSet  # noqa: E402

CACHE_DIR = BACKEND / "app" / "cache"
EVAL_DIR = BACKEND / "eval"
ACTIONS = {a.value for a in Action}

# Jury labels not in our vocabulary, mapped onto it.
_ALIAS = {"keep_optional": "keep"}


def parse_jury(action: str) -> tuple[set[str], str, bool]:
    """'remove_or_delay' -> ({'remove'}, 'remove', delay=True); 'better_explain_or_remove' -> ({'better_explain','remove'}, 'better_explain', False)."""
    acceptable: list[str] = []
    expect_delay = False
    for tok in action.strip().lower().split("_or_"):
        tok = _ALIAS.get(tok, tok)
        if tok == "delay":
            expect_delay = True
            tok = "remove"
        if tok in ACTIONS and tok not in acceptable:
            acceptable.append(tok)
    if not acceptable:
        raise ValueError(f"unparsable jury action '{action}'")
    return set(acceptable), acceptable[0], expect_delay


def checks_only_ruleset(form: FormSchema) -> RuleSet:
    return build_ruleset(form, run_checks(form), {f.field_id: None for f in form.fields}, ai_model=None, status="proposed")


def cached_ruleset(form: FormSchema) -> tuple[RuleSet, str]:
    p = CACHE_DIR / f"{form.form_id}.json"
    if p.exists():
        return RuleSet.model_validate_json(p.read_text(encoding="utf-8")), "cached"
    return checks_only_ruleset(form), "checks-only (no cache)"


def live_ruleset(form: FormSchema) -> tuple[RuleSet, str]:
    from app.ai.assess import assess_form
    from app.ai.client import get_client

    client = get_client()
    if not client.configured:
        print("Apertus not configured: set APERTUS_API_KEY in backend/.env (or use --checks-only / --cached).")
        sys.exit(2)
    assessments, errors = asyncio.run(assess_form(form, client=client))
    rs = build_ruleset(form, run_checks(form), assessments, ai_model=client.model, ai_errors=errors, status="proposed")
    return rs, f"live ({len(errors)} errors)" if errors else "live"


def main() -> int:
    ap = argparse.ArgumentParser()
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--checks-only", action="store_true")
    mode.add_argument("--cached", action="store_true")
    mode.add_argument("--live", action="store_true")
    ap.add_argument("--forms", help="comma-separated form ids (default: all)")
    args = ap.parse_args()

    forms, jury = load_workbook()
    wanted = {x.strip() for x in args.forms.split(",")} if args.forms else None
    forms = [f for f in forms if wanted is None or f.form_id in wanted]
    jury_by: dict[tuple[str, str], JuryLabel] = {(j.form_id, j.field_id): j for j in jury}

    lines: list[str] = []
    mismatches: list[str] = []
    totals = dict(n=0, flag=0, primary=0, lenient=0, delay_n=0, delay_hit=0, ai=0)
    lines.append("| form | source | n | flag acc | primary exact | lenient | delay hits | AI fields |")
    lines.append("|---|---|---|---|---|---|---|---|")

    for form in forms:
        if args.checks_only:
            rs, src = checks_only_ruleset(form), "checks-only"
        elif args.cached:
            rs, src = cached_ruleset(form)
        else:
            rs, src = live_ruleset(form)
        n = flag = primary = lenient = delay_n = delay_hit = ai = 0
        for rule in rs.rules:
            j = jury_by.get((form.form_id, rule.field_id))
            if j is None:
                continue
            acceptable, first, expect_delay = parse_jury(j.action)
            ours = {rule.action.value} | ({rule.alternative_action.value} if rule.alternative_action else set())
            n += 1
            ai += rule.ai is not None
            f_ok = (rule.action != Action.keep) == j.flag
            p_ok = rule.action.value == first
            l_ok = bool(ours & acceptable)
            flag += f_ok
            primary += p_ok
            lenient += l_ok
            if expect_delay:
                delay_n += 1
                delay_hit += Modifier.delay in rule.modifiers
            if not l_ok or not f_ok:
                mods = "+" + ",".join(m.value for m in rule.modifiers) if rule.modifiers else ""
                alt = f" (alt {rule.alternative_action.value})" if rule.alternative_action else ""
                sugg = f" [AI suggests {rule.ai_milder_suggestion.action.value}]" if rule.ai_milder_suggestion else ""
                mismatches.append(
                    f"- **{form.form_id} {rule.field_id}** — ours: `{rule.action.value}{mods}`{alt}{sugg} · jury: `{j.action}`\n"
                    f"  - ours: {rule.reason}\n  - jury: {j.reason}"
                )
        lines.append(f"| {form.form_id} {form.name} | {src} | {n} | {flag}/{n} | {primary}/{n} | {lenient}/{n} | {delay_hit}/{delay_n} | {ai}/{n} |")
        for k, v in dict(n=n, flag=flag, primary=primary, lenient=lenient, delay_n=delay_n, delay_hit=delay_hit, ai=ai).items():
            totals[k] += v

    t = totals
    lines.append(f"| **total** | | {t['n']} | **{t['flag']}/{t['n']}** | **{t['primary']}/{t['n']}** | **{t['lenient']}/{t['n']}** | {t['delay_hit']}/{t['delay_n']} | {t['ai']}/{t['n']} |")
    lines.append("")
    lines.append(f"Targets for the day: lenient ≥ 25/29, flag ≥ 27/29.")
    lines.append("")
    lines.append("## Mismatches (lenient or flag)")
    lines.extend(mismatches or ["- none"])
    text = "\n".join(lines)
    print(text)

    EVAL_DIR.mkdir(exist_ok=True)
    out = EVAL_DIR / f"results-{datetime.now():%Y%m%d-%H%M%S}.md"
    mode_name = "checks-only" if args.checks_only else "cached" if args.cached else "live"
    out.write_text(f"# Eval ({mode_name}) {datetime.now():%Y-%m-%d %H:%M}\n\n{text}\n", encoding="utf-8")
    print(f"\nwritten {out.relative_to(BACKEND)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
