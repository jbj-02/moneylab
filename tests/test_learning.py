"""Tests for contextual, nonjudgmental MoneyLab financial lessons."""

import pytest

from moneylab.learning import (
    LESSONS, check_answer, recommended_lesson_ids,
)


def test_lesson_content_has_questions_and_explanations():
    for ident, item in LESSONS.items():
        assert ident
        assert item["title"] and item["summary"] and item["explanation"]
        assert len(item["options"]) >= 2
        assert 0 <= item["answer"] < len(item["options"])
        assert item["feedback"]


def test_new_users_get_relevant_starting_lessons():
    recommended = recommended_lesson_ids([])
    assert recommended == ["paycheck", "budget", "savings"]


def test_existing_profile_drives_learning_context():
    blocks = [
        {"id": "income", "kind": "income", "monthly_amount": 3000, "name": "Salary"},
        {"id": "loan", "kind": "loan", "name": "Car loan"},
        {"id": "ira", "kind": "account", "account_type": "roth_ira",
         "name": "Retirement"},
    ]
    ids = recommended_lesson_ids(blocks)
    assert ids.index("paycheck") < ids.index("debt")
    assert "retirement" in ids
    assert "routing" in ids
    assert len(ids) == len(set(ids))


def test_correct_and_incorrect_quiz_answers():
    for key, lesson in LESSONS.items():
        correct = check_answer(key, lesson["answer"])
        assert correct["correct"] is True
        assert correct["explanation"] == lesson["feedback"]
        incorrect_index = next(i for i in range(len(lesson["options"]))
                               if i != lesson["answer"])
        incorrect = check_answer(key, incorrect_index)
        assert incorrect["correct"] is False
        assert "Not quite" in incorrect["explanation"]


@pytest.mark.parametrize("lesson_id,selected", [
    ("unknown", 0), ("budget", None), ("budget", 99),
    ("budget", True), ("budget", -1), ("budget", "1"),
])
def test_invalid_quiz_inputs_are_rejected(lesson_id, selected):
    with pytest.raises(ValueError):
        check_answer(lesson_id, selected)
