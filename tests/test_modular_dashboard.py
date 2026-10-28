"""Smoke tests for the native five-page MoneyLab interface."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


def start():
    return AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()


def navigate(app, page):
    return app.switch_page(f"pages/{page}").run()


def errors(app):
    return [str(e.message) for e in app.exception]


def load_example(app):
    button = next(
        b for b in app.sidebar.button if b.label == "Load optional example profile"
    )
    return button.click().run()


def test_home_starts_empty_and_uses_native_navigation():
    app = start()
    assert not errors(app), errors(app)
    assert app.session_state["ml_blocks"] == []
    assert "Your money journey starts here" in [
        text.value for text in app.markdown
    ] or any("Your money journey" in text.value for text in app.markdown)
    assert len(app.sidebar.radio) == 0
    assert len(app.sidebar.page_link) == 3
    assert any(x.label == "✨ Quick Start · set up or add finances"
               for x in app.sidebar.page_link)
    assert len(app.sidebar.slider) == 1


def test_sample_profile_and_home_metrics():
    app = load_example(start())
    assert not errors(app), errors(app)
    assert len(app.session_state["ml_blocks"]) == 10
    metrics = {x.label: x.value for x in app.metric}
    assert metrics["Monthly take-home"] == "$3,800.00"
    assert metrics["Additional monthly flexibility"] == "Review needed"
    assert any("check-in" in text.value.lower() for text in app.markdown)
    assert any(b.label == "✨ Quick Start · add more finances" for b in app.button)


def test_my_money_shows_existing_blocks():
    app = load_example(start())
    app = navigate(app, "1_My_Money.py")
    assert not errors(app), errors(app)
    assert any("My Money" in t.value for t in app.title)
    assert any("Take-home salary" in m.value for m in app.markdown)
    assert any(b.label == "＋ Add a block" for b in app.button)
    assert any(b.label == "✨ Quick Start · add multiple blocks"
               for b in app.button)


def test_goals_are_editable_blocks_with_clear_progress():
    app = load_example(start())
    app = navigate(app, "2_Goals.py")
    assert not errors(app), errors(app)
    assert any("Your goals" in t.value for t in app.title)
    assert any("Summer travel fund" in m.value for m in app.markdown)
    assert len(app.progress) >= 1
    assert any(b.label == "Edit goal" for b in app.button)


def test_decisions_page_keeps_advanced_whatif_available():
    app = load_example(start())
    app = navigate(app, "3_Explore.py")
    assert not errors(app), errors(app)
    assert any("MoneyLab Decision Check" in title.value for title in app.title)
    kinds = next(r for r in app.radio if r.label == "What would you like to figure out?")
    app = kinds.set_value("🔍 Explore an existing expense").run()
    assert not errors(app), errors(app)
    assert any("What would be different" in m.value for m in app.markdown)
    assert any(b.label == "Save scenario" for b in app.button)


def test_learning_remains_accessible():
    app = start()
    app = navigate(app, "4_Learn.py")
    assert not errors(app), errors(app)
    assert any("Learn by doing" in t.value for t in app.title)


def test_settings_supports_workspace_export_and_old_import():
    app = load_example(start())
    app = navigate(app, "6_Settings.py")
    assert not errors(app), errors(app)
    assert any("Settings & data" in t.value for t in app.title)
    assert len(app.get("download_button")) >= 1


def test_review_action_and_notes_remain_on_home():
    app = load_example(start())
    mark = next(b for b in app.button
                if b.label == "I've reviewed my entered financial information")
    app = mark.click().run()
    assert not errors(app), errors(app)
    assert app.session_state["ml_reviewed_signature"]
    # The example vacation goal misses its deadline, so a reviewed profile
    # still needs attention rather than receiving false reassurance.
    assert {m.label: m.value for m in app.metric}[
        "Additional monthly flexibility"
    ] == "Review needed"


def test_home_explains_single_next_step():
    app = load_example(start())
    assert not errors(app), errors(app)
    assert any("One useful next step" in item.value for item in app.markdown)
    assert any("Confirm your financial inputs" in item.value for item in app.markdown)
    assert any(b.label == "Review my figures" for b in app.button)


def test_decision_check_simulates_one_time_purchase_with_example():
    app = load_example(start())
    app = navigate(app, "3_Explore.py")
    assert not errors(app), errors(app)
    assert any(b.label == "Check this decision" for b in app.button)
    original_blocks = app.session_state["ml_blocks"].copy()
    run = next(b for b in app.button if b.label == "Check this decision")
    app = run.click().run()
    assert not errors(app), errors(app)
    assert app.session_state["ml_blocks"] == original_blocks
    assert any(x.label == "Checking immediately after" for x in app.metric)
    assert any(x.label.startswith("Net position change") for x in app.metric)


def test_reserve_check_and_goal_check_render_in_decisions():
    app = load_example(start())
    app = navigate(app, "3_Explore.py")
    selector = next(r for r in app.radio if r.label == "What would you like to figure out?")
    app = selector.set_value("🛟 How prepared am I?").run()
    assert not errors(app), errors(app)
    assert any(x.label == "Months of listed outflows" for x in app.metric)
    selector = next(r for r in app.radio if r.label == "What would you like to figure out?")
    app = selector.set_value("🎯 How do I reach a goal?").run()
    assert not errors(app), errors(app)
    assert any(x.label == "Planned monthly contribution" for x in app.metric)


def test_decision_check_offers_relevant_learning_without_changing_finances():
    app = load_example(start())
    app = navigate(app, "3_Explore.py")
    blocks = app.session_state["ml_blocks"].copy()
    button = next(b for b in app.button
                  if b.label == "Learn the concept behind this decision")
    app = button.click().run()
    assert not errors(app), errors(app)
    assert app.session_state["ml_lesson"] == "budget"
    assert app.session_state["ml_blocks"] == blocks


def test_decisions_empty_profile_recommends_setup():
    app = navigate(start(), "3_Explore.py")
    assert not errors(app), errors(app)
    assert any(b.label == "Start my profile" for b in app.button)
