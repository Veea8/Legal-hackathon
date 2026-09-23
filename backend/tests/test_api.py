import time

from fastapi.testclient import TestClient

from app.main import app


def _wait_for_analysis(client, sid, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = client.get(f"/api/forms/{sid}/analysis")
        assert r.status_code == 200, r.text
        if r.json()["status"] != "running":
            return r.json()
        time.sleep(0.05)
    raise AssertionError("analysis did not finish")


def test_health_kb_and_demo_forms():
    with TestClient(app) as client:
        r = client.get("/api/health")
        assert r.status_code == 200 and r.json()["ok"] is True
        assert len(client.get("/api/kb").json()) >= 15
        forms = client.get("/api/demo-forms").json()
        assert [f["form_id"] for f in forms] == ["F001", "F002", "F003", "F004", "F005"]
        assert forms[0]["n_fields"] == 8


def test_full_flow_without_ai_key():
    with TestClient(app) as client:
        r = client.post("/api/forms", json={"source": "demo", "form_id": "F001"})
        assert r.status_code == 200, r.text
        schema = r.json()
        sid = schema["form_id"]
        assert schema["name"] == "Telehealth App Signup" and len(schema["fields"]) == 8

        checks = client.get(f"/api/forms/{sid}/checks").json()
        assert {c["field_id"]: c["floor_action"] for c in checks}["mental_health_history"] == "remove"

        r = client.post(f"/api/forms/{sid}/analyze", params={"live": "true"})
        assert r.status_code == 200 and r.json()["status"] in ("running", "proposed")
        rs = _wait_for_analysis(client, sid)
        assert rs["status"] == "proposed" and len(rs["rules"]) == 8
        assert rs["fields_done"] == 8 and rs["cached"] is False

        # override below the floor without a note is refused
        r = client.put(f"/api/forms/{sid}/rules", json={"overrides": [{"field_id": "mental_health_history", "action": "keep"}]})
        assert r.status_code == 422
        r = client.put(f"/api/forms/{sid}/rules", json={"overrides": [
            {"field_id": "mental_health_history", "action": "keep", "note": "Clinical triage requires it; explicit consent flow added"},
            {"field_id": "passport_scan", "accept_alternative": True},
        ]})
        assert r.status_code == 200, r.text
        rules = {x["field_id"]: x for x in r.json()["rules"]}
        assert rules["mental_health_history"]["warning"] and rules["mental_health_history"]["source"] == "human"
        assert rules["passport_scan"]["action"] == "better_explain"
        assert rules["passport_scan"]["warning"].startswith("Alternative accepted below the compliance floor")

        r = client.post(f"/api/forms/{sid}/apply")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["report"]["summary"]["n_overrides_flagged"] == 2  # hard override + alternative below floor
        assert "passport_scan" in [f["field_id"] for f in body["minimised"]["fields"]]

        assert client.get(f"/api/forms/{sid}/report", params={"format": "csv"}).headers["content-type"].startswith("text/csv")
        assert "<h1>Data minimisation report</h1>" in client.get(f"/api/forms/{sid}/report", params={"format": "html"}).text
        assert client.get(f"/api/forms/{sid}/report").json()["form"]["name"] == "Telehealth App Signup"


def test_upload_csv_and_update_form():
    csv_text = (
        "form_id,form_name,business_context,field_order,field_name,field_label,field_type,required,"
        "data_category,sensitive_flag,purpose_stated,purpose_text,retention_days,system_destination,third_party_shared\n"
        "U1,Newsletter Signup,Marketing,1,email,Email,email,Y,personal,N,Y,Send the newsletter,365,CRM,N\n"
        "U1,Newsletter Signup,Marketing,2,religion,Religion,dropdown,Y,special_category,Y,N,,365,CRM,N\n"
    )
    with TestClient(app) as client:
        r = client.post("/api/forms/upload", files={"file": ("form.csv", csv_text.encode(), "text/csv")})
        assert r.status_code == 200, r.text
        schema = r.json()[0]
        sid = schema["form_id"]
        assert schema["source"] == "upload" and schema["stage"] == "entry"

        schema["fields"][1]["purpose_text"] = "Chaplaincy programme (opt-in)"
        r = client.put(f"/api/forms/{sid}", json=schema)
        assert r.status_code == 200
        checks = {c["field_id"]: c for c in client.get(f"/api/forms/{sid}/checks").json()}
        assert checks["religion"]["floor_action"] == "keep"  # purpose now stated, only required->C04 gone too
        assert client.get("/api/forms/nope").status_code == 404
