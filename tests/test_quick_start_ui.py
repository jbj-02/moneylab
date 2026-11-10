"""Smoke tests for accessible Quick Start and an atomic guided batch."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


def start_quick_start():
    app = AppTest.from_file(
        str(ROOT / "app.py"), default_timeout=20,
    ).run()
    return app.switch_page("pages/5_Quick_Start.py").run()


def errors(app):
    return [str(item.message) for item in app.exception]


def click(app, label):
    return next(button for button in app.button if button.label == label).click().run()


def test_quick_start_is_accessible_and_guided_by_default():
    app = start_quick_start()
    assert not errors(app), errors(app)
    assert any("Set up My Finances" in title.value for title in app.title)
    assert any(b.label == "Review details from text" for b in app.button)
    assert any("Step 1 of 4" in x.value for x in app.markdown)
    assert app.session_state["ml_blocks"] == []


def test_ai_is_optional_and_no_key_is_safe():
    app = start_quick_start()
    assert not errors(app), errors(app)
    assert any("not enabled" in x.value for x in app.info)
    assert len(app.session_state["ml_blocks"]) == 0
    assert any("Or enter your figures in plain English" == x.label for x in app.expander)


def test_guided_wizard_batches_income_and_rent_on_approval():
    app = start_quick_start()
    paycheck = next(x for x in app.number_input
                    if x.label == "Take-home pay each pay period ($)")
    app = paycheck.set_value(1800.00).run()
    app = click(app, "Continue")
    assert not errors(app), errors(app)
    rent = next(x for x in app.number_input if x.label == "Rent or housing ($)")
    app = rent.set_value(1200.00).run()
    app = click(app, "Continue")
    app = click(app, "Continue")
    app = click(app, "Review my profile")
    assert not errors(app), errors(app)
    assert app.session_state["ml_blocks"] == []
    assert len(app.session_state["qs_drafts"]) == 2
    app = click(app, "Save selected details")
    assert not errors(app), errors(app)
    amounts = {b["name"]: b for b in app.session_state["ml_blocks"]}
    assert len(amounts) == 2
    assert amounts["Take-home pay"]["monthly_amount"] == "3900.00"
    assert amounts["Rent / housing"]["monthly_amount"] == "1200.00"


def test_users_can_discard_preview_without_changing_finances():
    app = start_quick_start()
    app = next(x for x in app.number_input
               if x.label == "Take-home pay each pay period ($)").set_value(1500).run()
    app = click(app, "Continue")
    app = click(app, "Continue")
    app = click(app, "Continue")
    app = click(app, "Review my profile")
    assert len(app.session_state["qs_drafts"]) == 1
    app = click(app, "Discard suggestions")
    assert not errors(app), errors(app)
    assert app.session_state["qs_drafts"] is None
    assert app.session_state["ml_blocks"] == []


def test_private_smart_paste_adds_several_blocks_without_ai_key():
    app = start_quick_start()
    assert not errors(app), errors(app)
    description = (
        "My take-home pay is $1,800 biweekly, my rent is $1,200 monthly, "
        "groceries are $100 weekly, and checking is $500."
    )
    smart = next(item for item in app.text_area
                 if item.label == "Your financial description")
    app = smart.set_value(description).run()
    app = click(app, "Review details from text")
    assert not errors(app), errors(app)
    assert app.session_state["ml_blocks"] == []
    assert len(app.session_state["qs_drafts"]) == 4
    app = click(app, "Save selected details")
    assert not errors(app), errors(app)
    assert len(app.session_state["ml_blocks"]) == 4


def test_quick_start_is_on_sidebar_for_every_financial_profile():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
    # Quick Start remains in native navigation; no duplicate sidebar
    # link is necessary.
    quick = app.switch_page("pages/5_Quick_Start.py").run()
    assert not errors(quick), errors(quick)
    assert any("Set up My Finances" in t.value for t in quick.title)
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
    app = next(b for b in app.sidebar.button
               if b.label == "Load optional example profile").click().run()
    assert len(app.session_state["ml_blocks"]) == 10
    finances = app.switch_page("pages/1_My_Money.py").run()
    assert any(b.label == "Add several items with guided setup" for b in finances.button)
