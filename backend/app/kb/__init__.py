"""Curated legal knowledge base (GDPR + revFADP). The AI may only cite ids from here."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.models import KBEntry

KB_PATH = Path(__file__).with_name("legal_kb.json")


@lru_cache(maxsize=1)
def load_kb() -> list[KBEntry]:
    with KB_PATH.open(encoding="utf-8") as fh:
        return [KBEntry.model_validate(e) for e in json.load(fh)]


@lru_cache(maxsize=1)
def kb_index() -> dict[str, KBEntry]:
    return {e.id: e for e in load_kb()}


def kb_ids() -> set[str]:
    return set(kb_index())


def filter_known(ids: list[str]) -> list[str]:
    """Drop ids the KB does not know (the validator for AI citations)."""
    known = kb_index()
    seen: list[str] = []
    for i in ids:
        if i in known and i not in seen:
            seen.append(i)
    return seen


def kb_titles(ids: list[str]) -> list[str]:
    idx = kb_index()
    return [f"{idx[i].article} — {idx[i].title}" for i in ids if i in idx]


def kb_prompt_lines() -> str:
    """One line per entry, for the AI prompt."""
    return "\n".join(f"- {e.id}: {e.article} {e.title} — {e.plain_summary}" for e in load_kb())
