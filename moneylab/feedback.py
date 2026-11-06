"""Private, opt-in MoneyLab alpha feedback transport.

No financial values, session state, free-form decision descriptions, profile
names or user identifiers are attached automatically. The endpoint is
configured server-side. Only an approved Formspree HTTPS route is accepted.
"""
import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlparse

QUESTIONS = (
    ("trying", "What were you trying to do?", 400),
    ("problem", "What was confusing or went wrong?", 1200),
    ("better", "What would have helped?", 800),
)


def validate_feedback(answers):
    if not isinstance(answers, dict) or set(answers) != {q[0] for q in QUESTIONS}:
        raise ValueError("Complete the three feedback questions.")
    cleaned = {}
    for key, label, maximum in QUESTIONS:
        value = answers[key]
        if not isinstance(value, str) or not 4 <= len(value.strip()) <= maximum:
            raise ValueError(f"{label} must contain 4–{maximum} characters.")
        cleaned[key] = value.strip()
    return cleaned


def validate_endpoint(url):
    if not isinstance(url, str):
        raise ValueError("Private feedback endpoint is not configured.")
    url = url.strip()
    parsed = urlparse(url)
    if (parsed.scheme != "https" or parsed.hostname != "formspree.io"
            or parsed.username or parsed.password or parsed.port
            or parsed.query or parsed.fragment
            or not re.fullmatch(r"/f/[A-Za-z0-9]+", parsed.path)):
        raise ValueError(
            "Feedback endpoint must be a standard HTTPS Formspree form URL."
        )
    return url


def submit_private_feedback(answers, endpoint, *, opener=urlopen):
    """Send only the three reviewed comments; success requires a 2xx reply."""
    cleaned = validate_feedback(answers)
    url = validate_endpoint(endpoint)
    payload = json.dumps({
        "What were you trying to do?": cleaned["trying"],
        "What was confusing or went wrong?": cleaned["problem"],
        "What would have helped?": cleaned["better"],
        "Product": "MoneyLab alpha",
    }).encode("utf-8")
    if len(payload) > 4000:
        raise ValueError("Feedback is too long.")
    request = Request(
        url, data=payload, method="POST",
        headers={"Content-Type": "application/json",
                 "Accept": "application/json"},
    )
    try:
        with opener(request, timeout=8) as response:
            status = response.status
            if not 200 <= status < 300:
                raise ValueError(
                    "Feedback service did not confirm delivery. Try again later."
                )
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise ValueError(
            "Feedback was not confirmed delivered. Please retry later "
            "or save a local feedback copy."
        ) from exc
    return True


def feedback_draft(answers):
    values = validate_feedback(answers)
    return "\n\n".join(
        f"{label}\n{values[key]}" for key, label, _ in QUESTIONS
    ) + "\n"
