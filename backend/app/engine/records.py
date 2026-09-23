"""Record minimisation (planned, not built on hackathon day).

Intended entry point:

    apply_records(ruleset: RuleSet, rows: list[dict]) -> list[dict]

For each FieldRule.data_handling:
    delete       -> drop the column
    pseudonymise -> replace the value with a stable hash
    expire       -> null the value when the row is older than rule.retention_days
    retain       -> keep

The AI never sees `rows`; only the RuleSet (derived from field metadata) reaches this module.
"""

from __future__ import annotations

from app.models import RuleSet


def apply_records(ruleset: RuleSet, rows: list[dict]) -> list[dict]:  # pragma: no cover - stub
    raise NotImplementedError("Record minimisation is planned for after the schema path (decision D1).")
