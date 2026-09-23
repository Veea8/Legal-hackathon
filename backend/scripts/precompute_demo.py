"""Precompute cached RuleSets for the demo forms (decision D10). Run from backend/ after the key is in .env:

    ./.venv/bin/python scripts/precompute_demo.py [--forms F001,F003] [--allow-partial]

Writes app/cache/<form_id>.json (committed, so graders get instant results). A form is skipped when any
field errored, unless --allow-partial is given.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ai.assess import assess_form  # noqa: E402
from app.ai.client import get_client  # noqa: E402
from app.checks.rules import run_checks  # noqa: E402
from app.loaders.xlsx import load_demo_forms  # noqa: E402
from app.merge import build_ruleset  # noqa: E402

CACHE_DIR = Path(__file__).resolve().parents[1] / "app" / "cache"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--forms", help="comma-separated form ids (default: all)")
    ap.add_argument("--allow-partial", action="store_true", help="write the cache even if some fields errored")
    args = ap.parse_args()

    client = get_client()
    if not client.configured:
        print("Apertus not configured: set APERTUS_API_KEY (and base url / model) in backend/.env.")
        return 2

    wanted = {x.strip() for x in args.forms.split(",")} if args.forms else None
    forms = [f for f in load_demo_forms() if wanted is None or f.form_id in wanted]
    CACHE_DIR.mkdir(exist_ok=True)
    failed = 0
    for form in forms:
        print(f"{form.form_id} {form.name}: {len(form.fields)} fields ...", flush=True)
        checks = run_checks(form)

        def progress(fid, a, err, _form=form):
            print(f"   {fid:26s} {'ERR ' + err if err else a.proposed_action.value}")

        assessments, errors = asyncio.run(assess_form(form, client=client, on_field=progress))
        if errors and not args.allow_partial:
            print(f"   skipped: {len(errors)} field(s) errored (use --allow-partial to write anyway)")
            failed += 1
            continue
        rs = build_ruleset(form, checks, assessments, ai_model=client.model, ai_errors=errors, cached=True, status="proposed")
        out = CACHE_DIR / f"{form.form_id}.json"
        out.write_text(rs.model_dump_json(indent=2), encoding="utf-8")
        print(f"   wrote {out.relative_to(CACHE_DIR.parents[1])}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
