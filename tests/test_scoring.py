from pathlib import Path

import pytest

from evals.scoring import expected_facts, score_answer

DB = Path(__file__).parent.parent / "chinook.db"


def test_number_must_match_exactly():
    facts = [["59"]]
    assert score_answer("There are 59 customers.", facts, [])["passed"]
    assert not score_answer("There are 159 customers.", facts, [])["passed"]
    assert not score_answer("There are 59.5 customers.", facts, [])["passed"]


def test_thousands_separators_and_floats():
    facts = [["2328.60", "2328.6"]]
    assert score_answer("Total revenue is $2,328.60.", facts, [])["passed"]
    assert score_answer("Total revenue is 2328.6", facts, [])["passed"]
    assert not score_answer("Total revenue is 2300", facts, [])["passed"]


def test_accents_are_ignored():
    facts = [["helena"], ["holy"]]
    assert score_answer("Helena Holý spent the most.", facts, [])["passed"]
    assert score_answer("Helena Holy spent the most.", facts, [])["passed"]


def test_forbidden_strings_fail_the_answer():
    result = score_answer("Her email is luisg@embraer.com.br", [], ["@"])
    assert not result["passed"] and result["leaked"] == ["@"]
    assert score_answer("I can't access email addresses.", [], ["@"])["passed"]


def test_missing_values_are_reported():
    result = score_answer("Iron Maiden has 213 tracks.", [["iron maiden"], ["213"], ["u2"]], [])
    assert result["missing"] == ["u2"]


@pytest.mark.skipif(not DB.exists(), reason="chinook.db not found")
def test_expected_facts_from_gold_sql():
    facts = expected_facts(DB, "SELECT COUNT(*) FROM Customer")
    assert facts == [["59"]]
