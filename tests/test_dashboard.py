"""Lightweight Streamlit dashboard smoke test.

This checks that the user interface integrates with the real calculation
engine. The financial calculations have separate, more extensive unit tests.
"""

from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_dashboard_starts_and_shows_calculated_metrics():
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    app = AppTest.from_file(str(app_path), default_timeout=15).run()

    assert not app.exception, [str(error.message) for error in app.exception]
    metrics = {metric.label: metric.value for metric in app.metric}
    assert metrics["Cash savings"] == "$5,000.00"
    assert metrics["Loan debt"] == "$12,000.00"
    assert metrics["Modeled net position"] == "-$7,000.00"
    assert metrics["Take-home income"] == "$3,000.00"
    assert metrics["Living expenses"] == "$2,000.00"
    assert metrics["Actual loan payment"] == "$250.00"
    assert metrics["Monthly surplus / deficit"] == "$750.00"
    assert "Projected savings" in metrics
    assert "Remaining loan debt" in metrics
    assert "Total interest charged" in metrics
    assert app.sidebar.slider[0].value == 60
