"""Tests for beginner-friendly one-click finance templates."""

import pytest

from moneylab.blocks import validate_blocks, project_blocks
from moneylab.presets import PRESET_CATALOG, preset_block


@pytest.mark.parametrize("template", list(PRESET_CATALOG))
def test_all_presets_are_valid_and_work_in_projection(template):
    block = preset_block(template, "new_block_1")
    validated = validate_blocks([block])
    assert validated[0]["id"] == "new_block_1"
    projection = project_blocks([block], 1)
    assert len(projection["monthly_records"]) == 2


def test_duplicate_template_instances_have_separate_ids():
    a = preset_block("rent", "rent1")
    b = preset_block("rent", "rent2")
    assert a["name"] == b["name"]
    validate_blocks([a, b])


def test_template_edit_does_not_modify_catalog():
    instance = preset_block("hysa", "myhysa")
    instance["monthly_contribution"] = "900"
    assert PRESET_CATALOG["hysa"]["monthly_contribution"] == "100"


def test_unknown_preset_is_rejected():
    with pytest.raises(ValueError):
        preset_block("mystery", "x")


def test_invalid_generated_id_is_rejected():
    with pytest.raises(ValueError):
        preset_block("hysa", "bad id")
