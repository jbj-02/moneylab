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
    assert any("Moving Out Decision Lab" in x.value for x in app.title)
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
    mode = next(x for x in app.radio if x.label == "Where should we get the figures?")
    app = mode.set_value("Enter my own numbers").run()
    assert not errors(app), errors(app)
    assert app.session_state.get("move_result") is None
    assert len(app.get("download_button")) == 0


def test_missing_required_values_show_error_without_scenario():
    app = open_moving()
    mode = next(x for x in app.radio if x.label == "Where should we get the figures?")
    app = mode.set_value("Enter my own numbers").run()
    app = click_compare(app)
    assert not errors(app), errors(app)
    assert len(app.error) >= 1
    assert app.session_state.get("move_result") is None


def test_feedback_link_is_not_a_private_data_endpoint():
    app = open_moving()
    assert not errors(app), errors(app)
    links = app.get("page_link")
    assert any(b.label == "Share private alpha feedback" for b in links)
    assert app.session_state["ml_blocks"] == []


def test_home_promotes_decision_without_quick_start():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=25).run()
    assert not errors(app), errors(app)
    assert any(b.label == "🏡 Can I afford to move out?" for b in app.button)
    assert app.session_state["ml_blocks"] == []



def test_use_my_money_prefills_current_not_proposed_rent():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    load = next(b for b in app.sidebar.button
                if b.label == "Load optional example profile")
    app = load.click().run()
    original = list(app.session_state["ml_blocks"])
    app = app.switch_page("pages/7_Moving_Out_Alpha.py").run()
    mode = next(r for r in app.radio
                if r.label == "Where should we get the figures?")
    app = mode.set_value("Use My Money figures").run()
    assert not errors(app), errors(app)
    assert any(b.label == "Use My Money figures" for b in app.button)
    app = next(b for b in app.button
               if b.label == "Use My Money figures").click().run()
    assert not errors(app), errors(app)
    assert app.session_state["move_income"] == 3800.0
    assert app.session_state["move_current_housing"] == 1350.0
    assert app.session_state["move_other_living"] == 650.0
    assert app.session_state["move_minimum_debt"] == 470.0
    assert "move_rent" not in app.session_state
    assert app.session_state["ml_blocks"] == original


def test_edit_original_hides_old_results_and_recalculates_new_rent():
    app = click_compare(open_moving())
    assert not errors(app), errors(app)
    assert app.session_state["move_result"]["monthly_change"] == 1325
    edit = next(b for b in app.button
                if b.label == "Edit original assumptions")
    app = edit.click().run()
    assert not errors(app), errors(app)
    assert len(app.get("download_button")) == 0
    rent = next(x for x in app.number_input
                if x.label == "Your share of new rent ($/month)")
    rent.set_value(1000.00)
    app = click_compare(app)
    assert not errors(app), errors(app)
    assert app.session_state["move_result"]["monthly_change"] == 925
    assert any("Included in this comparison" in text.value
               for text in app.markdown)


def test_alternative_rent_keeps_original_comparison():
    app = click_compare(open_moving())
    original = app.session_state["move_result"]["monthly_change"]
    button = next(b for b in app.button if b.label == "Try lower rent")
    app = button.click().run()
    assert not errors(app), errors(app)
    compare = next(b for b in app.button
                   if b.label == "Compare this variation")
    app = compare.click().run()
    assert not errors(app), errors(app)
    assert app.session_state["move_result"]["monthly_change"] == original
    assert app.session_state["move_variant_result"]["monthly_change"] < original


def test_feedback_page_does_not_claim_unconfigured_submission():
    app = open_moving().switch_page("pages/8_Feedback.py").run()
    assert not errors(app), errors(app)
    assert any("Share feedback" in t.value for t in app.title)
    assert any("not configured" in w.value.lower() for w in app.warning)
    assert not any("delivered" in msg.value.lower() for msg in app.success)
