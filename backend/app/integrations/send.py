"""The only place in the app that sends anything outward besides the model call.

Rules it holds to, all of them for the same reason — a live demo must never hang or crash:
  * a bad URL is rejected before a socket is opened;
  * every failure mode returns a value, none of them raise;
  * the timeout budget is ~6 s worst case, and there are no retries. A demo wants a fast, visible
    failure in the log, not a thirty-second backoff.
The webhook URL is a secret: it is used once and only its redacted form is ever stored or returned.
"""

from __future__ import annotations

from typing import NamedTuple
from urllib.parse import urlsplit

import httpx

TIMEOUT = httpx.Timeout(connect=3.0, read=6.0, write=6.0, pool=3.0)


class SendResult(NamedTuple):
    ok: bool
    status: int | None
    detail: str


def validate_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        raise ValueError("Paste the incoming webhook URL first.")
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ValueError("That is not a valid http(s) webhook URL.")
    return url


def redact(url: str) -> str:
    """hooks.slack.com/…/B04f — enough to recognise, not enough to reuse."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return "(unparsable url)"
    host = parts.netloc or "?"
    tail = (parts.path or "").rstrip("/")[-4:]
    return f"{host}/…/{tail}" if tail else host


async def post_json(url: str, payload: dict) -> SendResult:
    """POST and describe the outcome. Never raises."""
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=False) as client:
            res = await client.post(url, json=payload, headers={"User-Agent": "minima/0.1"})
    except httpx.ConnectTimeout:
        return SendResult(False, None, "could not connect within 3s")
    except httpx.ReadTimeout:
        return SendResult(False, None, "no response within 6s")
    except httpx.HTTPError as exc:
        return SendResult(False, None, f"{type(exc).__name__}: {exc}"[:200])
    except Exception as exc:  # last resort: nothing here may reach the route
        return SendResult(False, None, f"{type(exc).__name__}: {exc}"[:200])

    body = (res.text or "").strip().replace("\n", " ")[:200]
    if 200 <= res.status_code < 300:
        return SendResult(True, res.status_code, body or f"{res.status_code} {res.reason_phrase}")
    # Slack's "invalid_token" and Teams' error text read well in the log — keep them.
    return SendResult(False, res.status_code, body or f"{res.status_code} {res.reason_phrase}")
