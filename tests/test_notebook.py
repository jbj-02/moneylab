"""Validate that the Colab submission notebook is structurally sound."""

import json
from pathlib import Path


def test_phase1_notebook_is_valid_and_has_compilable_python():
    notebook_file = (
        Path(__file__).resolve().parents[1] / "notebooks" / "phase1_demo.ipynb"
    )
    notebook = json.loads(notebook_file.read_text(encoding="utf-8"))
    assert notebook["nbformat"] == 4
    cells = notebook["cells"]
    assert any(cell["cell_type"] == "markdown" for cell in cells)

    code_cells = [cell for cell in cells if cell["cell_type"] == "code"]
    assert len(code_cells) >= 4
    for index, cell in enumerate(code_cells):
        code = "".join(cell["source"])
        compile(code, f"phase1_demo.ipynb:cell_{index + 1}", "exec")
    combined = "\n".join("".join(cell["source"]) for cell in code_cells)
    assert "project_finances(" in combined
    assert "compare_financial_strategies(" in combined
    assert "assert current" in combined
