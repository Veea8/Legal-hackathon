"""Latency / JSON-validity benchmark for the Apertus endpoint. Run from backend/:

    ./.venv/bin/python scripts/benchmark_apertus.py [--model ID] [--n 5] [--sequential]

Prints per-call latency, p50/p95, JSON-valid rate, whether json_object mode was accepted, and the model id.
An HTTP 401 in the output means the key is expired or wrong (re-issue via the Keymaker, update backend/.env).
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ai.assess import normalise_assessment  # noqa: E402
from app.ai.client import ApertusClient, get_client  # noqa: E402
from app.ai.prompts import SYSTEM_PROMPT, field_prompt  # noqa: E402
from app.kb import kb_prompt_lines  # noqa: E402
from app.loaders.xlsx import load_demo_forms  # noqa: E402

PICKS = [
    ("F001", "mental_health_history"),
    ("F001", "insurance_number"),
    ("F002", "personal_calendar_access"),
    ("F003", "dietary_preferences"),
    ("F004", "parent_occupation"),
    ("F005", "criminal_record_upload"),
    ("F003", "gender"),
    ("F002", "mobile_phone"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", help="override APERTUS_MODEL")
    ap.add_argument("--n", type=int, default=5, help="number of field prompts (max %d)" % len(PICKS))
    ap.add_argument("--sequential", action="store_true", help="one call at a time instead of concurrent")
    args = ap.parse_args()

    client = ApertusClient(model=args.model) if args.model else get_client()
    if not client.configured:
        print("Apertus not configured: set APERTUS_BASE_URL, APERTUS_API_KEY, APERTUS_MODEL in backend/.env "
              "(copy backend/.env.example).")
        return 2

    forms = {f.form_id: f for f in load_demo_forms()}
    picks = [(forms[fid], forms[fid].field(name)) for fid, name in PICKS[: max(1, args.n)]]
    kb = kb_prompt_lines()
    prompt_chars = len(SYSTEM_PROMPT) + len(field_prompt(picks[0][0], picks[0][1], kb))
    print(f"model={client.model} base_url={client.base_url}")
    print(f"prompt size ≈ {prompt_chars} chars (~{prompt_chars // 4} tokens); concurrency={client.concurrency} max_rps={client.max_rps}")

    results: list[tuple[str, float, bool, str]] = []

    async def one(form, field) -> None:
        t0 = time.perf_counter()
        try:
            raw = await client.complete_json(SYSTEM_PROMPT, field_prompt(form, field, kb))
            a = normalise_assessment(field.field_id, raw)
            ok, info = True, f"{a.proposed_action.value}{'+' + ','.join(m.value for m in a.modifiers) if a.modifiers else ''} (conf {a.confidence:.2f})"
        except Exception as exc:  # noqa: BLE001
            ok, info = False, f"{type(exc).__name__}: {str(exc)[:160]}"
        dt = time.perf_counter() - t0
        results.append((field.field_id, dt, ok, info))
        print(f"  {field.field_id:26s} {dt:6.1f}s  {'ok ' if ok else 'ERR'}  {info}")

    async def run() -> None:
        if args.sequential:
            for form, field in picks:
                await one(form, field)
        else:
            await asyncio.gather(*(one(form, field) for form, field in picks))

    t0 = time.perf_counter()
    asyncio.run(run())
    wall = time.perf_counter() - t0
    lat = sorted(r[1] for r in results)
    p50 = statistics.median(lat)
    p95 = lat[max(0, int(round(0.95 * (len(lat) - 1))))]
    valid = sum(1 for r in results if r[2])
    print(f"\ncalls={len(results)} wall={wall:.1f}s p50={p50:.1f}s p95={p95:.1f}s "
          f"json_valid={valid}/{len(results)} json_object_mode={client.json_mode}")
    if p50 > 15:
        print("p50 above 15 s per field: consider the 8B model on PublicAI (see docs/APERTUS.md).")
    return 0 if valid == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
