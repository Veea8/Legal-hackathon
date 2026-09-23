import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


import pytest


@pytest.fixture(autouse=True)
def no_live_ai(monkeypatch):
    """The suite never calls Apertus.

    Once a real key sits in backend/.env the client picks it up, and tests that expect the
    rule-based fallback would instead hit the network: slow, flaky and billed. Tests must pass
    identically with and without a key.
    """
    from app.ai import client as ai_client

    c = ai_client.get_client()
    monkeypatch.setattr(c, "api_key", "", raising=False)
    monkeypatch.setattr(c, "_client", None, raising=False)
    monkeypatch.setattr(ai_client.ApertusClient, "refresh_from_env", lambda self: self.configured, raising=False)
