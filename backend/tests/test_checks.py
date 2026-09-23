"""The 29 dataset rows: expected floor per field. The floor must never be stricter than the jury action,
except F003 dietary_preferences (deliberate showcase for AI + human judgement)."""

import pytest

from app.checks.rules import check_alternative, check_modifiers, run_checks
from app.loaders.xlsx import DEFAULT_WORKBOOK, load_workbook
from app.models import Action, Modifier

EXPECTED_FLOOR = {
    # F001 Telehealth
    ("F001", "first_name"): "keep",
    ("F001", "preferred_name"): "keep",
    ("F001", "date_of_birth"): "keep",
    ("F001", "insurance_number"): "keep",
    ("F001", "mental_health_history"): "remove",
    ("F001", "language_preference"): "keep",
    ("F001", "emergency_contact_name"): "make_optional",
    ("F001", "passport_scan"): "remove",
    # F002 B2B demo
    ("F002", "full_name"): "keep",
    ("F002", "work_email"): "keep",
    ("F002", "mobile_phone"): "make_optional",
    ("F002", "company_size"): "keep",
    ("F002", "annual_revenue"): "make_optional",
    ("F002", "current_vendor"): "keep",
    ("F002", "personal_calendar_access"): "remove",
    # F003 HR onboarding
    ("F003", "bank_account"): "keep",
    ("F003", "dietary_preferences"): "remove",  # jury: make_optional -> AI/human showcase
    ("F003", "religion"): "remove",
    ("F003", "home_address"): "keep",
    ("F003", "photo_upload"): "better_explain",
    ("F003", "gender"): "make_optional",
    # F004 Scholarship
    ("F004", "student_name"): "keep",
    ("F004", "household_income"): "keep",
    ("F004", "parent_occupation"): "make_optional",
    ("F004", "migration_status"): "make_optional",
    # F005 Volunteer
    ("F005", "display_name"): "keep",
    ("F005", "legal_sex"): "make_optional",
    ("F005", "shirt_size"): "keep",
    ("F005", "criminal_record_upload"): "remove",
}

PROTECTED = {"preferred_name", "language_preference", "company_size", "current_vendor", "shirt_size"}


@pytest.fixture(scope="module")
def results():
    forms, _ = load_workbook(DEFAULT_WORKBOOK)
    out = {}
    for form in forms:
        for r in run_checks(form):
            out[(form.form_id, r.field_id)] = r
    return out


def test_floor_matches_expected_table(results):
    mismatches = {
        k: (r.floor_action.value, EXPECTED_FLOOR[k]) for k, r in results.items()
        if r.floor_action.value != EXPECTED_FLOOR[k]
    }
    assert not mismatches, mismatches


def test_inclusive_optional_fields_are_protected(results):
    for (form_id, field_id), r in results.items():
        assert r.protected_inclusive == (field_id in PROTECTED), (form_id, field_id)
        if r.protected_inclusive:
            assert r.floor_action == Action.keep


def test_entry_stage_special_data_gets_delay_and_alternative(results):
    r = results[("F001", "mental_health_history")]
    assert Modifier.delay in check_modifiers(r)
    assert check_alternative(r) == Action.better_explain
    ids = [t.rule_id for t in r.triggered]
    assert "C02" in ids and "C04" in ids and "C06" in ids


def test_identity_document_and_oauth(results):
    assert "C07" in [t.rule_id for t in results[("F001", "passport_scan")].triggered]
    cal = results[("F002", "personal_calendar_access")]
    assert "C09" in [t.rule_id for t in cal.triggered]
    assert Modifier.delay in check_modifiers(cal)


def test_kb_refs_exist(results):
    from app.kb import kb_ids

    known = kb_ids()
    for r in results.values():
        for t in r.triggered:
            assert set(t.kb_refs) <= known, (r.field_id, t.rule_id, t.kb_refs)
