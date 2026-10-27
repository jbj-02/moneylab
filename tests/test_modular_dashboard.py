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
    assert len(app.sidebar.page_link) == 2
    assert len(app.sidebar.slider) == 1


def test_sample_profile_and_home_metrics():
    app = load_example(start())
    assert not errors(app), errors(app)
    assert len(app.session_state["ml_blocks"]) == 10
    metrics = {x.label: x.value for x in app.metric}
    assert metrics["Monthly take-home"] == "$3,800.00"
    assert metrics["Additional monthly flexibility"] == "Review needed"
    assert any("check-in" in text.value.lower() for text in app.markdown)


def test_my_money_shows_existing_blocks():
    app = load_example(start())
    app = navigate(app, "1_My_Money.py")
    assert not errors(app), errors(app)
    assert any("My Money" in t.value for t in app.title)
    assert any("Take-home salary" in m.value for m in app.markdown)
    assert any(b.label == "＋ Add a block" for b in app.button)


def test_goals_are_editable_blocks_with_clear_progress():
    app = load_example(start())
    app = navigate(app, "2_Goals.py")
    assert not errors(app), errors(app)
    assert any("Your goals" in t.value for t in app.title)
    assert any("Summer travel fund" in m.value for m in app.markdown)
    assert len(app.progress) >= 1
    assert any(b.label == "Edit goal" for b in app.button)


def test_explore_displays_impact_and_saved_scenarios():
    app = load_example(start())
    app = navigate(app, "3_Explore.py")
    assert not errors(app), errors(app)
    assert any("What would be different" in m.value for m in app.markdown)
    assert any(b.label == "Save scenario" for b in app.button)


def test_learning_remains_accessible():
    app = start()
    app = navigate(app, "4_Learn.py")
    assert not errors(app), errors(app)
    assert any("Learn by doing" in t.value for t in app.subheader)


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
    assert {m.label: m.value for m in app.metric}[
        "Additional monthly flexibility"
    ] == "$905.00"
