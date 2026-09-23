"""Form sessions, shared through Redis on Vercel and kept in memory locally."""

from __future__ import annotations

import json
import os
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
    def __init__(self, redis_client=None) -> None:
        self._sessions: dict[str, Session] = {}
        self._redis_client = redis_client

    def _redis(self):
        if self._redis_client is not None:
            return self._redis_client
        url = os.getenv("KV_REST_API_URL") or os.getenv("UPSTASH_REDIS_REST_URL")
        token = os.getenv("KV_REST_API_TOKEN") or os.getenv("UPSTASH_REDIS_REST_TOKEN")
        if not url and not token:
            if os.getenv("VERCEL"):
                raise RuntimeError("Redis session credentials are missing on Vercel")
            return None
        if not url or not token:
            raise RuntimeError("Redis session credentials are incomplete")
        from upstash_redis.asyncio import Redis

        self._redis_client = Redis(url=url, token=token, allow_telemetry=False)
        return self._redis_client

    @staticmethod
    def _key(sid: str) -> str:
        return f"minima:session:{sid}"

    @staticmethod
    def _decode(raw) -> Session:
        data = json.loads(raw) if isinstance(raw, str) else raw
        return Session(
            id=data["id"],
            schema=FormSchema.model_validate(data["schema"]),
            demo_form_id=data.get("demo_form_id"),
            checks=[CheckResult.model_validate(x) for x in data.get("checks", [])],
            ruleset=RuleSet.model_validate(data["ruleset"]) if data.get("ruleset") else None,
            minimised=MinimisedForm.model_validate(data["minimised"]) if data.get("minimised") else None,
            report=Report.model_validate(data["report"]) if data.get("report") else None,
            created_at=datetime.fromisoformat(data["created_at"]),
        )

    async def create(self, schema: FormSchema, *, demo_form_id: Optional[str] = None) -> Session:
        sid = uuid.uuid4().hex[:10]
        schema = schema.model_copy(deep=True)
        schema.form_id = sid
        s = Session(id=sid, schema=schema, demo_form_id=demo_form_id)
        await self.save(s)
        return s

    async def save(self, session: Session) -> None:
        redis = self._redis()
        if redis is None:
            self._sessions[session.id] = session
            return
        data = {
            "id": session.id,
            "schema": session.schema.model_dump(mode="json"),
            "demo_form_id": session.demo_form_id,
            "checks": [c.model_dump(mode="json") for c in session.checks],
            "ruleset": session.ruleset.model_dump(mode="json") if session.ruleset else None,
            "minimised": session.minimised.model_dump(mode="json") if session.minimised else None,
            "report": session.report.model_dump(mode="json") if session.report else None,
            "created_at": session.created_at.isoformat(),
        }
        await redis.set(self._key(session.id), json.dumps(data), exat=int(session.created_at.timestamp()) + 86400)

    async def get(self, sid: str) -> Optional[Session]:
        redis = self._redis()
        if redis is None:
            return self._sessions.get(sid)
        raw = await redis.get(self._key(sid))
        return self._decode(raw) if raw is not None else None

    def __len__(self) -> int:
        return len(self._sessions)


store = Store()
