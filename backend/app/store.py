"""In-memory session store. One process, one dict. Good enough for a hackathon demo."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from app.models import CheckResult, FormSchema, MinimisedForm, Report, RuleSet


@dataclass
class Session:
    id: str
    schema: FormSchema
    demo_form_id: Optional[str] = None  # set when created from a demo form (enables the cache)
    checks: list[CheckResult] = field(default_factory=list)
    ruleset: Optional[RuleSet] = None
    minimised: Optional[MinimisedForm] = None
    report: Optional[Report] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class Store:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def create(self, schema: FormSchema, *, demo_form_id: Optional[str] = None) -> Session:
        sid = uuid.uuid4().hex[:10]
        schema = schema.model_copy(deep=True)
        s = Session(id=sid, schema=schema, demo_form_id=demo_form_id)
        self._sessions[sid] = s
        return s

    def get(self, sid: str) -> Optional[Session]:
        return self._sessions.get(sid)

    def __len__(self) -> int:
        return len(self._sessions)


store = Store()
