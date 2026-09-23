import pytest

from app.checks.rules import run_checks
from app.engine.apply import apply
from app.loaders.xlsx import DEFAULT_WORKBOOK, load_workbook
from app.merge import OverrideError, apply_overrides, build_ruleset
from app.models import Action, AIAssessment, Modifier, RuleOverride
from app.report.build import build_report, render_csv, render_html


@pytest.fixture(scope="module")
def forms():
    return {f.form_id: f for f in load_workbook(DEFAULT_WORKBOOK)[0]}


def _ai(field_id, action, reason="because", **kw):
    return AIAssessment(field_id=field_id, proposed_action=action, reason=reason, **kw)


def test_merge_ai_missing_uses_floor(forms):
    form = forms["F001"]
    rs = build_ruleset(form, run_checks(form), {}, ai_model=None)
    mh = rs.rule("mental_health_history")
    assert mh.action == Action.remove and mh.proposed_action == Action.remove
    assert mh.source == "checks" and Modifier.delay in mh.modifiers
    assert mh.alternative_action == Action.better_explain
    assert rs.rule("preferred_name").action == Action.keep


def test_merge_ai_stricter_wins_and_milder_becomes_suggestion(forms):
    form = forms["F005"]
    ai = {
        "legal_sex": _ai("legal_sex", Action.remove, "No purpose for volunteers", kb_refs=["gdpr-5-1-c", "not-a-kb-id"]),
        "criminal_record_upload": _ai("criminal_record_upload", Action.make_optional, "Roles may need it",
                                      modifiers=[Modifier.role_based]),
    }
    rs = build_ruleset(form, run_checks(form), ai, ai_model="test")
    ls = rs.rule("legal_sex")
    assert ls.action == Action.remove and ls.source == "both" and not ls.disagreement
    assert "not-a-kb-id" not in ls.kb_refs and "gdpr-5-1-c" in ls.kb_refs
    cr = rs.rule("criminal_record_upload")
    assert cr.action == Action.remove  # floor wins
    assert cr.disagreement and cr.ai_milder_suggestion.action == Action.make_optional
    assert cr.source == "checks"


def test_overrides_warn_below_floor_and_require_note(forms):
    form = forms["F003"]
    ai = {"dietary_preferences": _ai("dietary_preferences", Action.make_optional, "Inclusive catering field if optional")}
    rs = build_ruleset(form, run_checks(form), ai, ai_model="test")
    with pytest.raises(OverrideError):
        apply_overrides(rs, [RuleOverride(field_id="religion", action=Action.keep)])
    rs = apply_overrides(rs, [
        RuleOverride(field_id="religion", action=Action.keep, note="Chaplaincy programme, consent-based"),
        RuleOverride(field_id="dietary_preferences", accept_ai_suggestion=True),
    ])
    rel = rs.rule("religion")
    assert rel.action == Action.keep and rel.warning and rel.human_override.note
    diet = rs.rule("dietary_preferences")
    assert diet.action == Action.make_optional and diet.source == "human" and diet.warning
    assert rs.status == "reviewed"
    rs = apply_overrides(rs, [RuleOverride(field_id="religion")])  # reset
    assert rs.rule("religion").action == Action.remove and rs.rule("religion").human_override is None


def test_engine_and_report_end_to_end(forms):
    form = forms["F001"]
    ai = {
        "emergency_contact_name": _ai("emergency_contact_name", Action.make_optional, "Not needed at signup",
                                      microcopy="Optional: someone we may contact in an emergency."),
        "insurance_number": _ai("insurance_number", Action.keep, "Needed for billing", microcopy="Used only to bill your insurer."),
        "passport_scan": _ai("passport_scan", Action.remove, "Excessive at signup", alternative_action=Action.better_explain),
    }
    rs = build_ruleset(form, run_checks(form), ai, ai_model="test")
    mini = apply(form, rs)
    ids = [f.field_id for f in mini.fields]
    assert "mental_health_history" not in ids and "passport_scan" not in ids
    assert [d.field_id for d in mini.delayed] == ["mental_health_history"]
    assert [r.field_id for r in mini.removed] == ["passport_scan"]
    ec = next(f for f in mini.fields if f.field_id == "emergency_contact_name")
    assert ec.required is False and ec.microcopy.startswith("Optional")
    assert mini.diff.made_optional == ["emergency_contact_name"]

    report = build_report(form, rs, mini)
    assert report.summary.n_fields == 8
    assert set(report.no_longer_collected) == {"Upload passport scan", "Mental health history"}
    assert any("Art. 9" in t for r in report.rows for t in r.kb_titles)
    csv_text = render_csv(report)
    assert "passport_scan" in csv_text and csv_text.count("\n") == 9
    html_text = render_html(report)
    assert "Data minimisation report" in html_text and "Telehealth App Signup" in html_text
