"""AI setup requests are bounded, review-only, and never auto-save."""
import json
from urllib import error

import pytest

from moneylab.ai_setup import (
    MAX_INPUT_CHARS, SCHEMA, extract_response_items,
    make_payload, suggest_financial_blocks,
)


def response_for(items):
    return {
        "status": "completed",
        "output": [
            {"type": "message", "content": [
                {"type": "output_text", "text": json.dumps({"items": items})},
            ]},
        ],
    }


def test_request_is_strict_review_only_and_storage_disabled():
    request_body = make_payload(
        "I earn 2000 dollars per month after taxes and pay 900 rent."
    )
    assert request_body["store"] is False
    assert request_body["text"]["format"]["strict"] is True
    assert request_body["text"]["format"]["type"] == "json_schema"
    fields = SCHEMA["properties"]["items"]["items"]
    assert fields["additionalProperties"] is False
    assert set(fields["required"]) == set(fields["properties"])
    assert all(block["role"] in ("system", "user") for block in request_body["input"])


@pytest.mark.parametrize("bad", [
    "", "hello", "x" * (MAX_INPUT_CHARS + 1), None,
])
def test_description_length_and_type_gated(bad):
    with pytest.raises(ValueError):
        make_payload(bad)


def test_structured_output_requires_review_for_missing_loan_details():
    draft = extract_response_items(response_for([{
        "kind": "loan", "name": "Student loan", "balance": 12000,
        "annual_rate": None, "monthly_payment": None,
    }]))
    assert draft[0]["missing"] == ["annual_rate", "monthly_payment"]


def test_rejects_incomplete_and_refused_model_answers():
    with pytest.raises(ValueError):
        extract_response_items({"status": "incomplete", "output": []})
    with pytest.raises(ValueError):
        extract_response_items({
            "status": "completed",
            "output": [{
                "type": "message", "content": [{"type": "refusal"}],
            }],
        })
    with pytest.raises(ValueError):
        extract_response_items(response_for("not-an-array"))


class FakeResponse:
    def __init__(self, data):
        self.data = json.dumps(data).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, size):
        return self.data[:size]


def test_stubbed_transport_never_calls_real_api():
    seen = {}

    def fake_transport(req, timeout):
        seen["uri"] = req.full_url
        seen["headers"] = dict(req.header_items())
        seen["payload"] = json.loads(req.data)
        assert timeout <= 20
        return FakeResponse(response_for([
            {"kind": "income", "name": "Net pay", "amount": 1900,
             "frequency": "biweekly"},
        ]))

    items = suggest_financial_blocks(
        "My net paycheck is 1900 dollars every two weeks.",
        "fake-private-key", transport=fake_transport,
    )
    assert seen["uri"] == "https://api.openai.com/v1/responses"
    assert seen["payload"]["store"] is False
    assert items[0]["amount"] == "1900"
    assert items[0]["frequency"] == "biweekly"


def test_transport_errors_show_non_sensitive_message():
    def failing_transport(req, timeout):
        raise error.URLError("sensitive provider error")
    with pytest.raises(ValueError, match="temporarily unavailable") as exc:
        suggest_financial_blocks(
            "I make 2000 net monthly and pay rent.",
            "fake-key", transport=failing_transport,
        )
    assert "sensitive" not in str(exc.value)
    assert "fake-key" not in str(exc.value)


def test_key_required_for_remote_setup():
    with pytest.raises(ValueError):
        suggest_financial_blocks("My rent is 1200 per month and I have savings.", "")
