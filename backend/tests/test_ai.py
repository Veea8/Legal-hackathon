"""Offline tests for the AI layer: no network, a FakeClient stands in for Apertus."""

import asyncio

import pytest

from app.ai.assess import assess_form, normalise_assessment
from app.ai.client import AIError, ApertusClient, extract_json
from app.ai.extract import extract_fields
from app.ai.prompts import SYSTEM_PROMPT, field_prompt
from app.kb import kb_prompt_lines
from app.loaders.xlsx import load_demo_forms
from app.models import Action, Modifier


class FakeClient:
    """`complete_json` returns canned dicts keyed by the field name found in the prompt, or raises."""

    model = "fake-model"
    configured = True

    def __init__(self, replies=None, fail_for=(), default=None):
        self.replies = replies or {}
        self.fail_for = set(fail_for)
        self.default = default or {"proposed_action": "keep", "reason": "fine", "confidence": 0.9}
        self.calls = []

    async def complete_json(self, system, user):
        self.calls.append(user)
        target = user.split("FIELD TO ASSESS: ", 1)[1].split("\n", 1)[0].strip() if "FIELD TO ASSESS: " in user else None
        if target in self.fail_for:
            raise AIError("boom")
        return self.replies.get(target, self.default)


def run(coro):
    return asyncio.run(coro)


@pytest.fixture(scope="module")
def f001():
    return load_demo_forms()[0]


# -- JSON extraction --------------------------------------------------------------

def test_extract_json_tolerates_fences_and_prose():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('Sure, here is the JSON:\n{"a": {"b": [1, 2]}}\nHope this helps.') == {"a": {"b": [1, 2]}}


def test_extract_json_errors():
    with pytest.raises(AIError):
        extract_json("no json here")
    with pytest.raises(AIError):
        extract_json('{"a": }')
    with pytest.raises(AIError):
        extract_json("[1, 2]")


# -- normalisation ------------------------------------------------------------------

def test_normalise_synonyms_and_compound_labels():
    a = normalise_assessment("x", {"proposed_action": "Optional", "reason": "  too   much  ", "confidence": 80})
    assert a.proposed_action == Action.make_optional and a.reason == "too much" and a.confidence == 0.8

    a = normalise_assessment("x", {"proposed_action": "drop", "modifiers": "delay, nonsense", "data_handling": "hash"})
    assert a.proposed_action == Action.remove and a.modifiers == [Modifier.delay] and a.data_handling == "pseudonymise"

    a = normalise_assessment("x", {"proposed_action": "remove_or_delay", "alternative_action": "explain"})
    assert a.proposed_action == Action.remove and Modifier.delay in a.modifiers
    assert a.alternative_action == Action.better_explain

    a = normalise_assessment("x", {"proposed_action": "make_optional_or_remove"})
    assert a.proposed_action == Action.make_optional and a.alternative_action == Action.remove


def test_normalise_filters_unknown_kb_ids_and_defaults():
    a = normalise_assessment("x", {
        "proposed_action": "remove", "kb_refs": ["gdpr-9", "GDPR-5-1-c", "gdpr-999", "made-up"],
        "necessity": "whatever", "retention_suggestion_days": "365 days", "microcopy": "null", "special_category": "yes",
    })
    assert a.kb_refs == ["gdpr-9", "gdpr-5-1-c"]
    assert a.necessity == "unclear" and a.retention_suggestion_days == 365
    assert a.microcopy is None and a.special_category is True and a.data_handling == "delete"
    assert a.reason == "No reason given by the model."


def test_normalise_requires_an_action():
    with pytest.raises(AIError):
        normalise_assessment("x", {"reason": "hm"})


# -- prompts ------------------------------------------------------------------------

def test_field_prompt_shows_siblings_and_never_values(f001):
    target = f001.field("mental_health_history")
    p = field_prompt(f001, target, kb_prompt_lines())
    assert "=> mental_health_history*" in p and "- first_name*" in p
    assert "NO PURPOSE STATED" in p and "gdpr-9:" in p
    assert "never see data values" in SYSTEM_PROMPT
    assert len(p) < 9000  # keep prompts compact


# -- assess_form ----------------------------------------------------------------------

def test_assess_form_progress_and_error_isolation(f001):
    client = FakeClient(
        replies={"mental_health_history": {"proposed_action": "remove", "modifiers": ["delay"], "reason": "too early", "kb_refs": ["gdpr-9"]}},
        fail_for={"passport_scan"},
    )
    seen = []
    results, errors = run(assess_form(f001, client=client, on_field=lambda fid, a, err: seen.append((fid, a is not None, err))))
    assert set(results) == {f.field_id for f in f001.fields}
    assert results["mental_health_history"].proposed_action == Action.remove
    assert results["passport_scan"] is None and "boom" in errors["passport_scan"]
    assert len(errors) == 1 and len(seen) == len(f001.fields)
    assert len(client.calls) == len(f001.fields)


def test_assess_form_not_configured_fast_path(f001):
    client = ApertusClient(base_url="", api_key="", model="")
    assert not client.configured
    results, errors = run(assess_form(f001, client=client))
    assert all(v is None for v in results.values()) and len(errors) == len(f001.fields)
    with pytest.raises(AIError):
        run(client.complete_json("s", "u"))


def test_callback_exceptions_do_not_break_analysis(f001):
    def bad_callback(*_):
        raise RuntimeError("ui exploded")

    results, errors = run(assess_form(f001, client=FakeClient(), on_field=bad_callback))
    assert not errors and all(results.values())


# -- extract ------------------------------------------------------------------------------

def test_extract_fields_shape():
    class ExtractFake(FakeClient):
        async def complete_json(self, system, user):
            return {"name": "Newsletter", "business_context": "Marketing", "fields": [
                {"name": "Email address", "label": "Email *", "type": "bogus", "required": None},
                {"label": "Upload passport scan", "required": "yes", "data_category": "Identity"},
                {"label": "Email address", "type": "email"},
                "garbage",
            ]}

    schema = run(extract_fields("Email *\nUpload passport scan", client=ExtractFake()))
    assert schema.source == "paste" and schema.name == "Newsletter"
    ids = [f.field_id for f in schema.fields]
    assert ids[0] == "email_address" and ids[1] == "upload_passport_scan" and ids[2] != ids[0]
    assert schema.fields[0].type == "email" and schema.fields[0].required and schema.fields[0].label == "Email"
    assert schema.fields[1].type == "file" and schema.fields[1].data_category == "identity"


def test_extract_requires_configured_client():
    with pytest.raises(AIError):
        run(extract_fields("x", client=ApertusClient(base_url="", api_key="", model="")))
