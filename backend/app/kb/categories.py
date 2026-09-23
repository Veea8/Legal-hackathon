"""Category normalisation: dataset labels (and free-text uploads) -> category groups used by the checks.

The challenge workbook uses labels such as `health`, `special_category_adjacent`, `business_financial`.
Own uploads may use anything; unknown labels fall back to PERSONAL with an info note.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional


class CategoryGroup(str, Enum):
    SPECIAL = "SPECIAL"  # GDPR Art. 9 / revFADP Art. 5 let. c
    CRIMINAL = "CRIMINAL"  # GDPR Art. 10 / revFADP Art. 5 let. c
    ADJACENT = "ADJACENT"  # gender, legal sex, migration status, profile photo: sensitive in effect
    IDENTITY_DOC = "IDENTITY_DOC"  # passport / ID scans
    FINANCIAL = "FINANCIAL"
    BEHAVIOURAL = "BEHAVIOURAL"  # tracking, integrations, calendar / contacts access
    PERSONAL = "PERSONAL"  # ordinary identifiers and contact data
    LOW = "LOW"  # preferences, business facts


_EXACT: dict[str, CategoryGroup] = {
    # SPECIAL
    "health": CategoryGroup.SPECIAL,
    "medical": CategoryGroup.SPECIAL,
    "special_category": CategoryGroup.SPECIAL,
    "biometric": CategoryGroup.SPECIAL,
    "genetic": CategoryGroup.SPECIAL,
    "religion": CategoryGroup.SPECIAL,
    "religious": CategoryGroup.SPECIAL,
    "ethnicity": CategoryGroup.SPECIAL,
    "ethnic": CategoryGroup.SPECIAL,
    "racial": CategoryGroup.SPECIAL,
    "sexual": CategoryGroup.SPECIAL,
    "sexual_orientation": CategoryGroup.SPECIAL,
    "political": CategoryGroup.SPECIAL,
    "union": CategoryGroup.SPECIAL,
    "trade_union": CategoryGroup.SPECIAL,
    "disability": CategoryGroup.SPECIAL,
    # CRIMINAL
    "criminal": CategoryGroup.CRIMINAL,
    "criminal_offence": CategoryGroup.CRIMINAL,
    "criminal_record": CategoryGroup.CRIMINAL,
    # ADJACENT
    "special_category_adjacent": CategoryGroup.ADJACENT,
    "biometric_adjacent": CategoryGroup.ADJACENT,
    "gender": CategoryGroup.ADJACENT,
    "sex": CategoryGroup.ADJACENT,
    "migration": CategoryGroup.ADJACENT,
    "nationality": CategoryGroup.ADJACENT,
    "photo": CategoryGroup.ADJACENT,
    # IDENTITY_DOC
    "identity": CategoryGroup.IDENTITY_DOC,
    "identity_document": CategoryGroup.IDENTITY_DOC,
    "id_document": CategoryGroup.IDENTITY_DOC,
    # FINANCIAL
    "financial": CategoryGroup.FINANCIAL,
    "business_financial": CategoryGroup.FINANCIAL,
    "payment": CategoryGroup.FINANCIAL,
    "bank": CategoryGroup.FINANCIAL,
    # BEHAVIOURAL
    "behavioral": CategoryGroup.BEHAVIOURAL,
    "behavioural": CategoryGroup.BEHAVIOURAL,
    "tracking": CategoryGroup.BEHAVIOURAL,
    "integration": CategoryGroup.BEHAVIOURAL,
    "location": CategoryGroup.BEHAVIOURAL,
    # PERSONAL
    "personal": CategoryGroup.PERSONAL,
    "personal_family": CategoryGroup.PERSONAL,
    "family": CategoryGroup.PERSONAL,
    "contact": CategoryGroup.PERSONAL,
    "identifier": CategoryGroup.PERSONAL,
    # LOW
    "preferences": CategoryGroup.LOW,
    "preference": CategoryGroup.LOW,
    "business": CategoryGroup.LOW,
    "company": CategoryGroup.LOW,
    "technical": CategoryGroup.LOW,
}

# Keyword hints used when a label is unknown (checked against label and field name, lower-cased).
_KEYWORDS: list[tuple[str, CategoryGroup]] = [
    ("criminal", CategoryGroup.CRIMINAL),
    ("conviction", CategoryGroup.CRIMINAL),
    ("religio", CategoryGroup.SPECIAL),
    ("health", CategoryGroup.SPECIAL),
    ("medical", CategoryGroup.SPECIAL),
    ("diagnos", CategoryGroup.SPECIAL),
    ("disab", CategoryGroup.SPECIAL),
    ("ethnic", CategoryGroup.SPECIAL),
    ("biometric", CategoryGroup.SPECIAL),
    ("passport", CategoryGroup.IDENTITY_DOC),
    ("id card", CategoryGroup.IDENTITY_DOC),
    ("id_scan", CategoryGroup.IDENTITY_DOC),
    ("gender", CategoryGroup.ADJACENT),
    ("legal_sex", CategoryGroup.ADJACENT),
    ("migration", CategoryGroup.ADJACENT),
    ("photo", CategoryGroup.ADJACENT),
    ("bank", CategoryGroup.FINANCIAL),
    ("iban", CategoryGroup.FINANCIAL),
    ("salary", CategoryGroup.FINANCIAL),
    ("income", CategoryGroup.FINANCIAL),
    ("revenue", CategoryGroup.FINANCIAL),
    ("calendar", CategoryGroup.BEHAVIOURAL),
    ("oauth", CategoryGroup.BEHAVIOURAL),
    ("tracking", CategoryGroup.BEHAVIOURAL),
    ("language", CategoryGroup.LOW),
    ("shirt", CategoryGroup.LOW),
    ("preference", CategoryGroup.LOW),
]


def normalise_category(
    data_category: Optional[str],
    *,
    field_name: str = "",
    label: str = "",
    field_type: str = "",
) -> tuple[CategoryGroup, bool]:
    """Return (group, known). `known` is False when we had to guess from keywords or fall back."""
    if data_category:
        key = data_category.strip().lower().replace(" ", "_").replace("-", "_")
        if key in _EXACT:
            return _EXACT[key], True
        if key.endswith("_adjacent"):
            return CategoryGroup.ADJACENT, True
    haystack = f"{field_name} {label} {data_category or ''}".lower()
    if field_type == "oauth":
        return CategoryGroup.BEHAVIOURAL, True
    for needle, group in _KEYWORDS:
        if needle in haystack:
            return group, False
    return CategoryGroup.PERSONAL, False


def is_special_or_criminal(group: CategoryGroup) -> bool:
    return group in (CategoryGroup.SPECIAL, CategoryGroup.CRIMINAL)
