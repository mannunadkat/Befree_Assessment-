"""Tests for Amount and Date Parsers."""

import pytest
from core.amount_date_parser import parse_date, parse_amount, is_valid_date, clean_amount_string


def test_parse_date_formats():
    assert parse_date("2024-01-15") == "2024-01-15"
    assert parse_date("15/01/2024") == "2024-01-15"
    assert parse_date("15-01-2024") == "2024-01-15"
    assert parse_date("15-Jan-2024") == "2024-01-15"
    assert parse_date("15 Jan 2024") == "2024-01-15"
    assert parse_date("Jan 15, 2024") == "2024-01-15"
    assert parse_date("05/03/24") == "2024-03-05"
    assert parse_date("invalid_date") is None
    assert is_valid_date("15/01/2024") is True
    assert is_valid_date("not a date") is False


def test_ocr_date_typos():
    # O instead of 0
    assert parse_date("1O/12/2024") == "2024-12-10"
    # l instead of 1
    assert parse_date("l5/01/2024") == "2024-01-15"


def test_parse_amount_formats():
    # Standard format
    assert parse_amount("1,234.56") == (1234.56, None)
    # Indian format (1,23,456.78)
    assert parse_amount("1,23,456.78") == (123456.78, None)
    # Negative with sign
    assert parse_amount("-450.00") == (450.0, "DR")
    # Negative with parentheses
    assert parse_amount("(1,200.50)") == (1200.50, "DR")
    # With Dr / Cr suffixes
    assert parse_amount("5,000.00 Dr") == (5000.0, "DR")
    assert parse_amount("12,500.00 Cr") == (12500.0, "CR")
    assert parse_amount("₹ 25,000.00") == (25000.0, None)
    assert parse_amount("INR 9,999.00") == (9999.0, None)
    assert parse_amount("-") == (None, None)
    assert parse_amount("0.00") == (0.0, None)


def test_ocr_amount_typos():
    # Spaces inside amount
    assert parse_amount("1 2, 4 5 0 . 0 0") == (12450.0, None)
    # Letter O instead of 0
    assert parse_amount("1O,OOO.OO") == (10000.0, None)


def test_resolve_split_debit_credit():
    from core.amount_date_parser import resolve_split_debit_credit
    # Integer in debit, decimal in credit
    assert resolve_split_debit_credit("1,250", ".50", 1250.0, 0.5) == (1250.5, None)
    assert resolve_split_debit_credit("1250.", "50", 1250.0, 50.0) == (1250.5, None)
    assert resolve_split_debit_credit("1250", "50", 1250.0, 50.0) == (1250.5, None)

    # Integer in credit, decimal in debit
    assert resolve_split_debit_credit(".75", "450", 0.75, 450.0) == (None, 450.75)
    assert resolve_split_debit_credit("75", "450.", 75.0, 450.0) == (None, 450.75)
    assert resolve_split_debit_credit("75", "450", 75.0, 450.0) == (None, 450.75)

    # Balance-guided resolution
    assert resolve_split_debit_credit("1250", "50", 1250.0, 50.0, last_balance=5000.0, current_balance=3749.50) == (1250.5, None)
    assert resolve_split_debit_credit("50", "1250", 50.0, 1250.0, last_balance=5000.0, current_balance=6250.50) == (None, 1250.5)
