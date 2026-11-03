"""Streamlit smoke tests for review-first Smart Decisions.

The interpreter must not modify saved financial blocks. Manual numbers and
the fictional demonstration must be kept separate after page transitions.
"""
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


def start():
    return AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()


def errors(app):
    return [str(error.message) for error in app.exception]


def enter_smart_request(app, sentence):
    box = next(x for x in app.text_area
               if x.label == "What are you thinking about doing?")
    app = box.set_value(sentence).run()
    button = next(x for x in app.button if x.label == "Understand my decision")
    return button.click().run()


def test_smart_moving_wizard_prefills_existing_moving_lab():
    app = enter_smart_request(
        start(),
        "I want to move out. The new rent is $1,500 monthly, "
        "my take-home pay is $3,500 monthly, and I have $8,000 saved.",
    )
    assert not errors(app), errors(app)
    assert app.session_state["ml_blocks"] == []
    assert app.session_state["smart_draft"]["intent"] == "moving"
    assert any("Review: Moving to a different home" in m.value
               for m in app.markdown)
    confirm = next(b for b in app.button
                   if b.label == "Open my decision with these values")
    app = confirm.click().run()
    assert not errors(app), errors(app)
    assert app.session_state["ml_blocks"] == []
    assert app.session_state["move_start_mode"] == "Enter my own numbers"
    assert app.session_state["move_rent"] == 1500.0
    assert app.session_state["move_income"] == 3500.0
    assert app.session_state["move_savings"] == 8000.0


def test_gross_salary_never_becomes_takehome_and_not_saved():
    app = enter_smart_request(
        start(),
        "I want to move out and rent an apartment for $1,800 monthly. "
        "My salary is $60,000 gross per year.",
    )
    assert not errors(app), errors(app)
    assert "income" in app.session_state["smart_draft"]["missing"]
    assert app.session_state["ml_blocks"] == []
    assert any("not" in w.message or "not" in w.value for w in app.warning)


def test_unsupported_language_does_not_open_financial_scenario():
    app = enter_smart_request(
        start(),
        "Should I refinance my student loans and change my investment portfolio?",
    )
    assert not errors(app), errors(app)
    assert app.session_state["smart_draft"]["intent"] == "unsupported"
    assert not any(b.label == "Open my decision with these values" for b in app.button)
    assert app.session_state["ml_blocks"] == []


def test_recurring_decision_carries_frequency_to_guest_page():
    app = enter_smart_request(
        start(),
        "I want a gym membership that costs $45 per month. "
        "My net take-home pay is $3,000 monthly.",
    )
    assert not errors(app), errors(app)
    assert app.session_state["smart_draft"]["intent"] == "recurring"
    confirm = next(b for b in app.button
                   if b.label == "Open my decision with these values")
    app = confirm.click().run()
    assert not errors(app), errors(app)
    assert app.session_state["ml_blocks"] == []
    assert app.session_state["dc_guest_cost_kind"] == "recurring"
    assert app.session_state["dc_guest_frequency"] == "monthly"
    assert app.session_state["dc_guest_cost"] == 45.0


def test_existing_profile_not_overwritten_by_smart_scenario():
    app = start()
    example = next(b for b in app.sidebar.button
                   if b.label == "Load optional example profile")
    app = example.click().run()
    original = list(app.session_state["ml_blocks"])
    app = enter_smart_request(
        app, "I want to buy a vacation for $3,000 this summer."
    )
    confirm = next(b for b in app.button
                   if b.label == "Open my decision with these values")
    app = confirm.click().run()
    assert not errors(app), errors(app)
    assert app.session_state["ml_blocks"] == original
    assert app.session_state["dc_cost_kind"] == "One-time purchase"
    assert app.session_state["dc_cost_value"] == 3000.0
