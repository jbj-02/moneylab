"""Streamlit smoke tests for the empty-first financial workspace."""

from pathlib import Path

from streamlit.testing.v1 import AppTest


def start():
    return AppTest.from_file(
        str(Path(__file__).resolve().parents[1] / "app.py"),
        default_timeout=15,
    ).run()


def errors(app):
    return [str(error.message) for error in app.exception]


def test_homepage_starts_empty_without_misleading_metrics():
    app = start()
    assert not errors(app), errors(app)
    assert app.session_state["ml_blocks"] == []
    assert "Monthly take-home income" not in {m.label for m in app.metric}
    assert len(app.tabs) == 7
    assert app.sidebar.slider[0].value == 24


def test_example_profile_can_be_loaded_and_cleared():
    app = start()
    load = next(
        button for button in app.sidebar.button
        if button.label == "Load optional example profile"
    )
    app = load.click().run()
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
    assert "Monthly take-home income" not in {m.label for m in app.metric}


def test_onboarding_adds_only_one_suggested_block():
    app = start()
    button = next(
        b for b in app.button
        if b.label == "Add my first suggested block"
    )
    app = button.click().run()
    assert not errors(app), errors(app)
    assert len(app.session_state["ml_blocks"]) == 1
    assert app.session_state["ml_blocks"][0]["kind"] == "income"


def test_checkin_requires_explicit_profile_review():
    app = start()
    app = next(
        button for button in app.sidebar.button
        if button.label == "Load optional example profile"
    ).click().run()
    assert not errors(app), errors(app)
    mark = next(
        button for button in app.button
        if button.label == "I've reviewed my entered financial information"
    )
    app = mark.click().run()
    assert not errors(app), errors(app)
    assert app.session_state["ml_reviewed_signature"]
    assert "My check-in" in [t.label for t in app.tabs]
    assert "Learn" in [t.label for t in app.tabs]


def test_user_can_add_a_financial_template():
    app = start()
    add = next(button for button in app.button if button.label == "Add this building block")
    app = add.click().run()
    assert not errors(app), errors(app)
    assert len(app.session_state["ml_blocks"]) == 1
    assert app.session_state["ml_blocks"][-1]["kind"] == "income"


def test_reordering_blocks_keeps_all_blocks():
    app = start()
    app = next(
        button for button in app.sidebar.button
        if button.label == "Load optional example profile"
    ).click().run()
    original = [item["id"] for item in app.session_state["ml_blocks"]]
    move = next(button for button in app.button if button.label == "Move down")
    app = move.click().run()
    assert not errors(app), errors(app)
    moved = [item["id"] for item in app.session_state["ml_blocks"]]
    assert moved[:2] == original[1::-1]
    assert set(moved) == set(original)
