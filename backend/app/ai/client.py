"""Apertus client (OpenAI-compatible endpoint, see docs/APERTUS.md).

Contract used by the rest of the app:
    client = get_client()                 # cached, configured from env / backend/.env
    client.configured                     # base url + key + model all set
    await client.complete_json(system, user) -> dict   # concurrency + rate limited, tolerant JSON parsing
    ai_model_name() / ai_available() / json_mode_supported()

Anything with `complete_json(system, user)` and a `model` attribute can stand in for the client (tests use a fake).
Never logs or prints the key.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[2]
ENV_PATH = BACKEND_DIR / ".env"
load_dotenv(ENV_PATH)


class AIError(RuntimeError):
    """Clear, user-facing failure of the AI layer (configuration, HTTP, timeout, unparsable output)."""


def _env(name: str, default: str) -> str:
    v = os.getenv(name)
    return v if v not in (None, "") else default


def extract_json(text: Optional[str]) -> dict[str, Any]:
    """Tolerant JSON extraction: strips code fences and prose, takes the first `{` to the last `}`."""
    if not text or not text.strip():
        raise AIError("empty response")
    s = text.strip()
    s = re.sub(r"^```[a-zA-Z]*\s*", "", s)
    s = re.sub(r"\s*```\s*$", "", s)
    start, end = s.find("{"), s.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise AIError("no JSON object in response")
    try:
        obj = json.loads(s[start : end + 1])
    except json.JSONDecodeError as exc:
        raise AIError(f"invalid JSON: {exc.msg} at position {exc.pos}") from exc
    if not isinstance(obj, dict):
        raise AIError("JSON is not an object")
    return obj


class _RateLimiter:
    """Minimum interval between call starts, shared across coroutines of one event loop."""

    def __init__(self, rps: float) -> None:
        self.interval = 1.0 / rps if rps > 0 else 0.0
        self._next = 0.0
        self._lock = asyncio.Lock()

    async def wait(self) -> None:
        if self.interval <= 0:
            return
        async with self._lock:
            now = time.monotonic()
            delay = self._next - now
            if delay > 0:
                await asyncio.sleep(delay)
            self._next = max(now, self._next) + self.interval


class ApertusClient:
    def __init__(
        self,
        *,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        self.base_url = base_url if base_url is not None else _env("APERTUS_BASE_URL", "")
        self.api_key = api_key if api_key is not None else _env("APERTUS_API_KEY", "")
        self.model = model if model is not None else _env("APERTUS_MODEL", "")
        self.temperature = float(_env("AI_TEMPERATURE", "0.2"))
        self.max_tokens = int(_env("AI_MAX_TOKENS", "400"))
        self.timeout_s = float(_env("AI_TIMEOUT_S", "25"))
        self.concurrency = int(_env("AI_CONCURRENCY", "4"))
        self.max_rps = float(_env("AI_MAX_RPS", "4"))
        self.user_agent = _env("USER_AGENT", "data-minimiser-hackathon/0.1")
        self.json_mode: Optional[bool] = None  # None = not probed yet
        self._client: Any = None
        self._loop: Any = None
        self._sem: Optional[asyncio.Semaphore] = None
        self._limiter: Optional[_RateLimiter] = None

    # -- configuration -------------------------------------------------------

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.api_key and self.model)

    def refresh_from_env(self) -> bool:
        """Pick up a key / model added to backend/.env after start-up. True if now configured."""
        if self.configured:
            return True
        load_dotenv(ENV_PATH, override=True)
        self.base_url = self.base_url or _env("APERTUS_BASE_URL", "")
        self.api_key = self.api_key or _env("APERTUS_API_KEY", "")
        self.model = self.model or _env("APERTUS_MODEL", "")
        self._client = None
        return self.configured

    def _reload_key(self) -> bool:
        """Re-read the key from .env / environment (keys can be re-issued). True if it changed."""
        load_dotenv(ENV_PATH, override=True)
        new = os.getenv("APERTUS_API_KEY", "")
        if new and new != self.api_key:
            self.api_key = new
            self._client = None
            return True
        return False

    def _openai(self) -> Any:
        if self._client is None:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
                default_headers={"User-Agent": self.user_agent},
                timeout=self.timeout_s,
                max_retries=0,
            )
        return self._client

    def _primitives(self) -> tuple[asyncio.Semaphore, _RateLimiter]:
        loop = asyncio.get_running_loop()
        if self._loop is not loop or self._sem is None or self._limiter is None:
            self._loop = loop
            self._sem = asyncio.Semaphore(max(1, self.concurrency))
            self._limiter = _RateLimiter(self.max_rps)
        return self._sem, self._limiter

    # -- calls ---------------------------------------------------------------

    async def _raw(self, messages: list[dict[str, str]], *, json_mode: bool) -> str:
        kwargs: dict[str, Any] = dict(
            model=self.model, messages=messages, temperature=self.temperature, max_tokens=self.max_tokens
        )
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = await asyncio.wait_for(self._openai().chat.completions.create(**kwargs), timeout=self.timeout_s)
        return resp.choices[0].message.content or ""

    async def complete_json(self, system: str, user: str) -> dict[str, Any]:
        if not self.configured:
            raise AIError("Apertus not configured: set APERTUS_BASE_URL, APERTUS_API_KEY and APERTUS_MODEL in backend/.env")
        from openai import APIConnectionError, APIStatusError, APITimeoutError

        sem, limiter = self._primitives()
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        key_retried = parse_retried = False
        async with sem:
            while True:
                await limiter.wait()
                use_json = self.json_mode is not False
                try:
                    text = await self._raw(messages, json_mode=use_json)
                    if use_json and self.json_mode is None:
                        self.json_mode = True
                except APIStatusError as exc:
                    status = getattr(exc, "status_code", None)
                    if status == 400 and use_json and self.json_mode is not True:
                        self.json_mode = False  # server rejects response_format; retry without it
                        continue
                    if status == 401 and not key_retried:
                        key_retried = True
                        if self._reload_key():
                            continue
                        raise AIError(
                            "HTTP 401: the Apertus key was rejected (expired or wrong). "
                            "Re-issue it via the Keymaker and update backend/.env."
                        ) from exc
                    if status == 429:
                        raise AIError("HTTP 429: rate limit hit (Swisscom allows 5 req/s). Lower AI_MAX_RPS.") from exc
                    raise AIError(f"HTTP {status}: {str(getattr(exc, 'message', exc))[:200]}") from exc
                except (asyncio.TimeoutError, APITimeoutError) as exc:
                    raise AIError(f"timed out after {self.timeout_s:.0f}s") from exc
                except APIConnectionError as exc:
                    raise AIError(f"connection error: {str(exc)[:200]}") from exc

                try:
                    return extract_json(text)
                except AIError as exc:
                    if parse_retried:
                        raise AIError(f"unparsable reply after retry: {exc}") from exc
                    parse_retried = True
                    messages = messages + [
                        {"role": "assistant", "content": text},
                        {"role": "user", "content": f"Your reply was not valid JSON ({exc}). Reply again with ONLY the JSON object."},
                    ]


# -- module-level helpers ------------------------------------------------------

_client: Optional[ApertusClient] = None


def get_client() -> ApertusClient:
    global _client
    if _client is None:
        _client = ApertusClient()
    return _client


def ai_model_name() -> Optional[str]:
    c = get_client()
    return c.model if c.refresh_from_env() else None


def ai_available() -> bool:
    return get_client().refresh_from_env()


def json_mode_supported() -> Optional[bool]:
    return get_client().json_mode
