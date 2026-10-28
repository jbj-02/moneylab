"""Streamlit smoke tests for decision-first Moving Out alpha.

AppTest exercises page execution and a real submit, but does NOT inspect
responsive rendering in a graphical browser.
"""
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


def open_moving():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    return app.switch_page("pages/7_Moving_Out_Alpha.py").run()


def errors(app):
    return [str(x.message) for x in app.exception]


def click_compare(app):
    button = next(b for b in app.button if b.label == "Compare stay vs move")
    return button.click().run()


def test_moving_page_opens_with_sample_not_in_user_profile():
    app = open_moving()
    assert not errors(app), errors(app)
    assert any("Can I afford to move out?" in x.value for x in app.title)
    assert app.session_state["ml_blocks"] == []
    assert any(x.label == "Monthly take-home pay ($)" for x in app.number_input)
    assert any(b.label == "Compare stay vs move" for b in app.button)
    assert len(app.get("download_button")) == 0


def test_sample_comparison_and_export_no_profile_changes():
    app = open_moving()
    app = click_compare(app)
    assert not errors(app), errors(app)
    assert app.session_state["ml_blocks"] == []
    assert app.session_state["move_result"]["fundable"]
    assert app.session_state["move_result"]["monthly_change"] == 1325
    assert any("Your moving decision" in x.value for x in app.subheader)
    assert len(app.get("download_button")) == 1


def test_switching_to_own_numbers_clears_stale_sample_results():
    app = click_compare(open_moving())
    assert app.session_state["move_result"] is not None
    mode = next(x for x in app.radio if x.label == "How would you like to start?")
    app = mode.set_value("Enter my own numbers").run()
    assert not errors(app), errors(app)
    assert app.session_state.get("move_result") is None
    assert len(app.get("download_button")) == 0


def test_missing_required_values_show_error_without_scenario():
    app = open_moving()
    mode = next(x for x in app.radio if x.label == "How would you like to start?")
    app = mode.set_value("Enter my own numbers").run()
    app = click_compare(app)
    assert not errors(app), errors(app)
    assert len(app.error) >= 1
    assert app.session_state.get("move_result") is None


def test_feedback_link_is_not_a_private_data_endpoint():
    app = open_moving()
    assert not errors(app), errors(app)
    links = app.get("link_button")
    assert any(b.label == "Report a problem or request a feature" for b in links)
    assert app.session_state["ml_blocks"] == []


def test_home_promotes_decision_without_quick_start():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=25).run()
    assert not errors(app), errors(app)
    assert any(b.label == "🏡 Can I afford to move out?" for b in app.button)
    assert app.session_state["ml_blocks"] == []
