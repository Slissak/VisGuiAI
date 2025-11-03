import pytest
from src.utils.sorting import (
    natural_sort_key,
    sort_step_identifiers,
    is_identifier_before,
    get_next_identifier,
    get_previous_identifier
)

def test_natural_sort_key():
    assert natural_sort_key("0") == (0, "")
    assert natural_sort_key("1") == (1, "")
    assert natural_sort_key("1a") == (1, "a")
    assert natural_sort_key("1b") == (1, "b")
    assert natural_sort_key("10") == (10, "")
    assert natural_sort_key("10a") == (10, "a")

def test_sort_step_identifiers():
    input_ids = ["2", "1a", "10", "1", "1b", "0"]
    expected = ["0", "1", "1a", "1b", "2", "10"]
    assert sort_step_identifiers(input_ids) == expected

def test_is_identifier_before():
    assert is_identifier_before("1", "2") == True
    assert is_identifier_before("1a", "1b") == True
    assert is_identifier_before("1a", "1") == False
    assert is_identifier_before("1", "1a") == True
    assert is_identifier_before("2", "10") == True

def test_get_next_identifier():
    ids = ["0", "1", "1a", "1b", "2"]
    assert get_next_identifier("0", ids) == "1"
    assert get_next_identifier("1", ids) == "1a"
    assert get_next_identifier("1a", ids) == "1b"
    assert get_next_identifier("1b", ids) == "2"
    assert get_next_identifier("2", ids) is None

def test_get_previous_identifier():
    ids = ["0", "1", "1a", "1b", "2"]
    assert get_previous_identifier("0", ids) is None
    assert get_previous_identifier("1", ids) == "0"
    assert get_previous_identifier("1a", ids) == "1"
    assert get_previous_identifier("2", ids) == "1b"