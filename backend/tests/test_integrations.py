"""Integrations: payload shape, calendar correctness, and that nothing ever leaves without a valid URL.

No test here opens a socket. Previews are pure; the two send tests are rejected by `validate_url`
before httpx is reached, and the timeout test monkeypatches the client.
"""

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.integrations import ics, payloads, send
from app.main import app
from app.report.build import representative_tasks


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def sid(client):
    """A demo form taken all the way to an applied report, with one deletion deadline set."""
    s = client.post("/api/forms", json={"source": "demo", "form_id": "F001"}).json()["form_id"]
    client.post(f"/api/forms/{s}/analyze?live=false")
    r = client.put(f"/api/forms/{s}/rules", json={"overrides": [{"field_id": "date_of_birth", "retention_days": 90}]})
    assert r.status_code == 200, r.text
    assert client.post(f"/api/forms/{s}/apply").status_code == 200
    return s


@pytest.fixture
def report(client, sid):
    # Through the API, not the store: the store is async and Redis-backed in production.
    from app.models import Report
    return Report.model_validate(client.post(f"/api/forms/{sid}/apply").json()["report"])


def test_payload_builders_agree_with_the_checklist(report):
    tasks = representative_tasks(report)
    assert tasks, "the F001 demo form should produce a checklist"

    teams = payloads.teams_card(report, report_url="http://x/r")
    assert teams["type"] == "message"
    assert teams["attachments"][0]["contentType"] == "application/vnd.microsoft.card.adaptive"
    assert teams["attachments"][0]["content"]["version"] == "1.4"
    json.dumps(teams)

    slack = payloads.slack_blocks(report, report_url="http://x/r")
    assert len(slack["blocks"]) <= 50, "Slack rejects a message over 50 blocks"
    for b in slack["blocks"]:
        if isinstance(b.get("text"), dict):
            assert len(b["text"]["text"]) <= 3000, "Slack rejects a text object over 3000 chars"
    assert slack["text"], "a notification fallback is required"

    json.dumps(payloads.webhook_payload(report))

    issues = payloads.jira_issues(report, project_key="PRIV")
    assert len(issues) == len(tasks)
    assert len({i["key"] for i in issues}) == len(issues), "ticket keys must be unique"
    assert all(i["key"].startswith("PRIV-") for i in issues)
    assert all(len(i["summary"]) <= 120 for i in issues)

    mail = payloads.email_message(report, to="dpo@x.test", report_url="http://x/r")
    assert mail["attachment_bytes"] > 0 and mail["subject"]
    # Outlook and Gmail choke on a long mailto; the short body is deliberate.
    assert len(payloads.mailto_link(report, to="dpo@x.test", report_url="http://x/r")) < 2000


def test_ics_is_well_formed(report):
    cal = ics.render_ics(report, sid="sess1234")
    n = ics.n_deadlines(report)
    assert n >= 1

    assert cal.startswith("BEGIN:VCALENDAR\r\n") and cal.rstrip().endswith("END:VCALENDAR")
    assert cal.count("BEGIN:VEVENT") == cal.count("END:VEVENT") == n
    assert cal.count("BEGIN:VALARM") == n
    # Outlook rejects bare LF: every newline must be CRLF.
    assert "\n" in cal and cal.replace("\r\n", "") .count("\n") == 0

    lines = cal.split("\r\n")
    starts = [l for l in lines if l.startswith("DTSTART")]
    ends = [l for l in lines if l.startswith("DTEND")]
    assert len(starts) == len(ends) == n
    # DTEND is exclusive for an all-day event: same-day would render zero-length.
    from datetime import datetime, timedelta
    for s, e in zip(starts, ends):
        ds = datetime.strptime(s.split(":")[1], "%Y%m%d")
        de = datetime.strptime(e.split(":")[1], "%Y%m%d")
        assert de - ds == timedelta(days=1)

    assert ics._esc("Health, history; notes\\x") == "Health\\, history\\; notes\\\\x"
    assert all(len(l.encode()) <= 75 for l in lines), "content lines must be folded at 75 octets"


def test_preview_works_for_every_destination(client, sid):
    for d in ("teams", "slack", "webhook", "email", "jira", "calendar"):
        r = client.post(f"/api/forms/{sid}/deliveries/preview", json={"destination": d, "to": "dpo@x.test"})
        assert r.status_code == 200, d
        body = r.json()
        assert body["body"], d
        assert body["sendable"] is (d in ("teams", "slack", "webhook")), d
    assert client.get(f"/api/forms/{sid}/report?format=ics").status_code == 200


def test_send_rejects_a_bad_url_without_opening_a_socket(client, sid, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("no HTTP call may be made for an invalid URL")

    monkeypatch.setattr(httpx, "AsyncClient", boom)
    for url in ("", "not-a-url", "ftp://x/y"):
        rec = client.post(f"/api/forms/{sid}/deliveries", json={"destination": "teams", "url": url}).json()["record"]
        assert rec["ok"] is False and rec["detail"]
    assert len(client.get(f"/api/forms/{sid}/deliveries").json()) == 3

    # email / jira / calendar hand you the payload; there is nothing to send.
    assert client.post(f"/api/forms/{sid}/deliveries", json={"destination": "jira"}).status_code == 422


def test_a_timeout_is_logged_not_raised(client, sid, monkeypatch):
    async def timeout(url, payload):
        return send.SendResult(False, None, "no response within 6s")

    monkeypatch.setattr(send, "post_json", timeout)
    r = client.post(f"/api/forms/{sid}/deliveries",
                    json={"destination": "slack", "url": "https://hooks.slack.com/services/T0/B04/secret"})
    assert r.status_code == 200
    rec = r.json()["record"]
    assert rec["ok"] is False and rec["detail"] == "no response within 6s"
    assert "secret" not in json.dumps(r.json()), "the webhook URL must be stored redacted"


def test_delivery_log_survives_a_schema_edit(client, sid, monkeypatch):
    client.post(f"/api/forms/{sid}/deliveries", json={"destination": "teams", "url": "nope"})
    schema = client.get(f"/api/forms/{sid}").json()
    assert client.put(f"/api/forms/{sid}", json=schema).status_code == 200
    assert len(client.get(f"/api/forms/{sid}/deliveries").json()) == 1, "the audit trail is not analysis state"


def test_a_forgotten_session_can_be_rebuilt_from_the_client(client):
    """The store is in memory, so a restart or a recycled container loses every session.

    The browser keeps the schema, so it can rebuild one rather than dead-ending on
    "Unknown form '<id>'" — and passing the demo id back keeps the precomputed cache reachable.
    """
    first = client.post("/api/forms", json={"source": "demo", "form_id": "F001"}).json()
    schema = client.get(f"/api/forms/{first['form_id']}").json()
    schema["jurisdiction"] = "both"

    assert client.get("/api/forms/c009f518e1/analysis").status_code == 404

    rebuilt = client.post("/api/forms", json={"source": "schema", "schema": schema, "demo_form_id": "F001"})
    assert rebuilt.status_code == 200
    sid = rebuilt.json()["form_id"]
    assert sid != first["form_id"]
    assert rebuilt.json()["jurisdiction"] == "both", "the context answers survive the rebuild"

    rs = client.post(f"/api/forms/{sid}/analyze?live=false").json()
    assert rs["cached"] is True and rs["status"] == "proposed"
    assert client.post(f"/api/forms/{sid}/apply").status_code == 200

    assert client.post("/api/forms", json={"source": "schema"}).status_code == 422
