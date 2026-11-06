"""No private financial details are attached to alpha feedback requests."""
import json
from urllib.error import URLError
import pytest

from moneylab.feedback import (
    validate_feedback, validate_endpoint,
    submit_private_feedback, feedback_draft,
)

GOOD = {
    "trying": "Compare rent scenarios",
    "problem": "I did not know where utilities were shown.",
    "better": "Show monthly expenses near the results.",
}


class _Response:
    status = 200
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass


def test_private_feedback_posts_only_three_approved_answers():
    seen = {}
    def fake(request, timeout):
        seen["url"] = request.full_url
        seen["headers"] = dict(request.header_items())
        seen["payload"] = json.loads(request.data.decode("utf-8"))
        return _Response()
    assert submit_private_feedback(
        GOOD, "https://formspree.io/f/abcxyz",
        opener=fake,
    )
    assert seen["url"] == "https://formspree.io/f/abcxyz"
    assert seen["payload"]["What were you trying to do?"] == GOOD["trying"]
    assert "checking" not in json.dumps(seen["payload"]).lower()
    assert "profile" not in json.dumps(seen["payload"]).lower()
    assert len(seen["payload"]) == 4


@pytest.mark.parametrize("bad", [
    "http://formspree.io/f/abcxyz",
    "https://formspree.io.evil.example/f/abc",
    "https://github.com/user/repo/issues/new",
    "https://formspree.io/f/abc?income=2000",
    "https://evil.com/f/abc",
    "https://formspree.io:8080/f/abc",
    "",
])
def test_untrusted_feedback_destinations_rejected(bad):
    with pytest.raises(ValueError):
        validate_endpoint(bad)


def test_failed_feedback_delivery_is_not_success():
    def offline(request, timeout):
        raise URLError("offline")
    with pytest.raises(ValueError, match="not confirmed delivered"):
        submit_private_feedback(
            GOOD, "https://formspree.io/f/abcxyz", opener=offline
        )


@pytest.mark.parametrize("bad", [
    {"trying": "x", "problem": "confusing", "better": "help"},
    {"trying": "hello", "problem": "broken", "better": "fix", "income": "3000"},
    {"trying": 12, "problem": "bad", "better": "fix"},
])
def test_malformed_feedback_not_sent(bad):
    with pytest.raises(ValueError):
        validate_feedback(bad)


def test_downloadable_feedback_draft_is_not_marked_delivered():
    data = feedback_draft(GOOD)
    assert data.count("What") == 3
    assert GOOD["better"] in data
    assert "sent" not in data.lower()
