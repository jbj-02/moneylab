"""Streamlit smoke tests for the focused MoneyLab navigation and workflows."""

from pathlib import Path

from streamlit.testing.v1 import AppTest


def start():
    return AppTest.from_file(
        str(Path(__file__).resolve().parents[1] / "app.py"),
        default_timeout=15,
    ).run()


def errors(app):
    return [str(error.message) for error in app.exception]


def navigate(app, text):
    return app.sidebar.radio[0].set_value(text).run()


def load_example(app):
    return next(
        button for button in app.sidebar.button
        if button.label == "Load optional example profile"
    ).click().run()


def test_empty_onboarding_and_clean_navigation():
    app = start()
    assert not errors(app), errors(app)
    assert app.session_state["ml_blocks"] == []
    assert "Monthly take-home income" not in {m.label for m in app.metric}
    assert len(app.tabs) == 0
    assert len(app.sidebar.radio) == 1
    assert len(app.sidebar.radio[0].options) == 7
    assert app.sidebar.slider[0].value == 24


def test_load_example_and_clear():
    app = load_example(start())
    assert not errors(app), errors(app)
    assert len(app.session_state["ml_blocks"]) == 10
    metrics = {metric.label: metric.value for metric in app.metric}
    assert metrics["Monthly take-home income"] == "$3,800.00"
    assert metrics["Monthly bills & spending"] == "$2,000.00"
    assert metrics["Required loan payments"] == "$470.00"
    assert metrics["Planned savings transfers"] == "$425.00"
    assert metrics["Unallocated monthly buffer"] == "$905.00"
    assert metrics["Estimated extra weekly spend"] == "Review needed"
    empty = next(
        button for button in app.sidebar.button
        if button.label == "Start with an empty profile"
    )
    app = empty.click().run()
    assert not errors(app), errors(app)
    assert app.session_state["ml_blocks"] == []


def test_guided_first_block():
    app = start()
    button = next(
        item for item in app.button
        if item.label == "Add my first suggested block"
    )
    app = button.click().run()
    assert not errors(app), errors(app)
    assert len(app.session_state["ml_blocks"]) == 1
    assert app.session_state["ml_blocks"][0]["kind"] == "income"


def test_building_blocks_suggestions_and_reordering():
    app = navigate(start(), "🧱 Building blocks")
    assert not errors(app), errors(app)
    add = next(
        button for button in app.button
        if button.label == "Add this building block"
    )
    app = add.click().run()
    assert not errors(app), errors(app)
    assert len(app.session_state["ml_blocks"]) == 1
    assert app.session_state["ml_blocks"][0]["kind"] == "income"

    app = load_example(app)
    app = navigate(app, "🧱 Building blocks")
    original = [item["id"] for item in app.session_state["ml_blocks"]]
    move = next(button for button in app.button if button.label == "Move down")
    app = move.click().run()
    assert not errors(app), errors(app)
    moved = [item["id"] for item in app.session_state["ml_blocks"]]
    assert moved[:2] == original[1::-1]
    assert set(moved) == set(original)


def test_add_goal_using_quick_action():
    app = navigate(start(), "🧱 Building blocks")
    goal = next(
        button for button in app.button
        if button.label == "➕ Emergency fund goal"
    )
    app = goal.click().run()
    assert not errors(app), errors(app)
    assert app.session_state["ml_blocks"][0]["kind"] == "goal"
    app = navigate(app, "🎯 Goals & insights")
    assert not errors(app), errors(app)


def test_checkin_reviewer_and_lessons():
    app = load_example(start())
    app = navigate(app, "🧭 My check-in")
    assert not errors(app), errors(app)
    mark = next(
        button for button in app.button
        if button.label == "I've reviewed my entered financial information"
    )
    app = mark.click().run()
    assert not errors(app), errors(app)
    assert app.session_state["ml_reviewed_signature"]
    app = navigate(app, "📚 Learn")
    assert not errors(app), errors(app)
    assert app.session_state["ml_navigation"] == "📚 Learn"


def test_whatif_and_export_navigation():
    app = load_example(start())
    app = navigate(app, "🔬 What-if Lab")
    assert not errors(app), errors(app)
    assert any(b.label == "Save to my scenarios" for b in app.button)
    app = navigate(app, "🗂️ Data & export")
    assert not errors(app), errors(app)
    assert any(
        "workspace" in b.label.lower()
        for b in app.get("button")
    ) or app.get("download_button")
