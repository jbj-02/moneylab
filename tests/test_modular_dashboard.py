"""Streamlit smoke tests for MoneyLab's modular personalization homepage."""

from pathlib import Path

from streamlit.testing.v1 import AppTest


def start():
    return AppTest.from_file(
        str(Path(__file__).resolve().parents[1] / "app.py"),
        default_timeout=15,
    ).run()


def test_modular_homepage_loads_and_explains_value():
    app = start()
    assert not app.exception, [error.message for error in app.exception]
    metrics = {metric.label: metric.value for metric in app.metric}
    assert metrics["Monthly take-home income"] == "$3,800.00"
    assert metrics["Monthly bills & spending"] == "$2,000.00"
    assert metrics["Required loan payments"] == "$470.00"
    assert metrics["Planned savings transfers"] == "$425.00"
    assert metrics["Unallocated monthly buffer"] == "$905.00"
    assert metrics["Estimated extra weekly spend"] == "$208.85"
    assert "Projected net position" in metrics
    assert app.sidebar.slider[0].value == 24
    assert len(app.tabs) == 5


def test_empty_workspace_does_not_crash():
    app = start()
    clear = next(
        button for button in app.sidebar.button
        if button.label == "Start with an empty profile"
    )
    app = clear.click().run()
    assert not app.exception, [error.message for error in app.exception]
    assert app.session_state["ml_blocks"] == []
    metrics = {metric.label: metric.value for metric in app.metric}
    assert metrics["Monthly take-home income"] == "$0.00"
    assert metrics["Unallocated monthly buffer"] == "$0.00"


def test_user_can_add_a_financial_template():
    app = start()
    add = next(button for button in app.button if button.label == "Add this building block")
    app = add.click().run()
    assert not app.exception, [error.message for error in app.exception]
    assert len(app.session_state["ml_blocks"]) == 11
    assert app.session_state["ml_blocks"][-1]["kind"] == "income"


def test_reordering_blocks_keeps_all_blocks():
    app = start()
    original = [item["id"] for item in app.session_state["ml_blocks"]]
    move = next(button for button in app.button if button.label == "Move down")
    app = move.click().run()
    assert not app.exception, [error.message for error in app.exception]
    moved = [item["id"] for item in app.session_state["ml_blocks"]]
    assert moved[:2] == original[1::-1]
    assert set(moved) == set(original)
