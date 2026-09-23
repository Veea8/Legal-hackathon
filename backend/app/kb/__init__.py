"""Curated legal knowledge base (GDPR + revFADP). The AI may only cite ids from here."""

from __future__ import annotations

import json
import re
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


# A citation nobody can look up is decoration: every article gets a URL to the official text.
# GDPR -> gdpr-info.eu article pages; revFADP -> Fedlex SR 235.1 (the English consolidated text).
_FEDLEX = "https://www.fedlex.admin.ch/eli/cc/2022/491/en"


def kb_url(entry: KBEntry) -> str | None:
    """Link to the article itself. `Art. 6(6)-(7) revFADP` -> article 6."""
    m = re.search(r"(\d+)", entry.article)
    if not m:
        return None
    n = m.group(1)
    return f"https://gdpr-info.eu/art-{n}-gdpr/" if entry.law == "gdpr" else f"{_FEDLEX}#art_{n}"


def kb_cite(entry: KBEntry) -> str:
    """FADP entries already carry 'revFADP' inside the article string; do not say it twice."""
    if entry.law == "gdpr":
        return f"GDPR {entry.article}"
    return f"revFADP {re.sub(r'\s*revFADP\s*', ' ', entry.article, flags=re.I).strip()}"


def kb_refs(ids: list[str]) -> list[tuple[str, str, str | None]]:
    """(citation, title, url) per known id, for rendering linked references."""
    idx = kb_index()
    return [(kb_cite(idx[i]), idx[i].title, kb_url(idx[i])) for i in ids if i in idx]


def kb_prompt_lines() -> str:
    """One line per entry, for the AI prompt."""
    return "\n".join(f"- {e.id}: {e.article} {e.title} — {e.plain_summary}" for e in load_kb())
