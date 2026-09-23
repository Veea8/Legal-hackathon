"""Form sessions, shared through Redis on Vercel and kept in memory (and on disk) locally."""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from app.models import CheckResult, DeliveryRecord, FormSchema, MinimisedForm, Report, RuleSet

# Locally the sessions also go to disk: restarting uvicorn (or reloading on a file save) used to
# lose every open form, and the UI could only answer "Unknown form '<id>'" when a decision was
# confirmed. Redis owns the sessions wherever it is configured; this only backs the in-memory dict.
SESSION_DIR = Path(os.getenv("SESSION_DIR") or Path(__file__).resolve().parents[1] / ".sessions")
SESSION_TTL = timedelta(hours=24)


@dataclass
class Session:
    id: str
    schema: FormSchema
    demo_form_id: Optional[str] = None  # set when created from a demo form (enables the cache)
    checks: list[CheckResult] = field(default_factory=list)
    ruleset: Optional[RuleSet] = None
    minimised: Optional[MinimisedForm] = None
    report: Optional[Report] = None
    # Outbound deliveries that actually left the machine. An audit trail, so it survives a
    # schema edit that clears the analysis below it.
    deliveries: list[DeliveryRecord] = field(default_factory=list)
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
    def _encode(session: Session) -> dict:
        return {
            "id": session.id,
            "schema": session.schema.model_dump(mode="json"),
            "demo_form_id": session.demo_form_id,
            "checks": [c.model_dump(mode="json") for c in session.checks],
            "ruleset": session.ruleset.model_dump(mode="json") if session.ruleset else None,
            "minimised": session.minimised.model_dump(mode="json") if session.minimised else None,
            "report": session.report.model_dump(mode="json") if session.report else None,
            "deliveries": [d.model_dump(mode="json") for d in session.deliveries],
            "created_at": session.created_at.isoformat(),
        }

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
            deliveries=[DeliveryRecord.model_validate(x) for x in data.get("deliveries", [])],
            created_at=datetime.fromisoformat(data["created_at"]),
        )

    async def create(self, schema: FormSchema, *, demo_form_id: Optional[str] = None) -> Session:
        sid = uuid.uuid4().hex[:10]
        schema = schema.model_copy(deep=True)
        schema.form_id = sid
        s = Session(id=sid, schema=schema, demo_form_id=demo_form_id)
        await self.save(s)
        return s

    # -- local disk mirror -------------------------------------------------

    @staticmethod
    def _path(sid: str) -> Path:
        return SESSION_DIR / f"{sid}.json"

    def _write_disk(self, session: Session) -> None:
        try:
            SESSION_DIR.mkdir(parents=True, exist_ok=True)
            tmp = self._path(session.id).with_suffix(".tmp")
            tmp.write_text(json.dumps(self._encode(session)), encoding="utf-8")
            tmp.replace(self._path(session.id))
        except OSError:
            pass  # read-only filesystem: memory still holds the session for this process

    def _read_disk(self, sid: str) -> Optional[Session]:
        path = self._path(sid)
        try:
            session = self._decode(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, KeyError):
            return None
        if datetime.now(timezone.utc) - session.created_at > SESSION_TTL:
            path.unlink(missing_ok=True)
            return None
        return session

    # ----------------------------------------------------------------------

    async def save(self, session: Session) -> None:
        redis = self._redis()
        if redis is None:
            self._sessions[session.id] = session
            self._write_disk(session)
            return
        data = self._encode(session)
        await redis.set(self._key(session.id), json.dumps(data), exat=int(session.created_at.timestamp()) + 86400)

    async def get(self, sid: str) -> Optional[Session]:
        redis = self._redis()
        if redis is None:
            session = self._sessions.get(sid)
            if session is None:
                session = self._read_disk(sid)
                if session is not None:
                    self._sessions[sid] = session
            return session
        raw = await redis.get(self._key(sid))
        return self._decode(raw) if raw is not None else None

    def __len__(self) -> int:
        return len(self._sessions)


store = Store()
