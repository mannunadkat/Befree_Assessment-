"""Tests for Balance Validator and Auto-Repair."""

from core.models import Transaction
from core.validator import reconcile_and_repair_transactions


def test_validator_clean():
    txns = [
        Transaction(date="2024-01-01", description="Txn 1", debit=500.0, balance=9500.0),
        Transaction(date="2024-01-02", description="Txn 2", credit=2000.0, balance=11500.0),
        Transaction(date="2024-01-03", description="Txn 3", debit=1500.0, balance=10000.0),
    ]
    repaired_txns, report = reconcile_and_repair_transactions(txns, opening_balance=10000.0, closing_balance=10000.0)
    assert report.is_reconciled is True
    assert report.ok_rows == 3
    assert report.repaired_rows == 0
    assert report.mismatch_rows == 0
    assert report.total_debits == 2000.0
    assert report.total_credits == 2000.0


def test_validator_auto_repair_swapped_columns():
    # In row 2, a debit of 1000 was mistakenly parsed as credit
    txns = [
        Transaction(date="2024-01-01", description="Txn 1", debit=500.0, balance=9500.0),
        Transaction(date="2024-01-02", description="Txn 2", credit=1000.0, balance=8500.0),  # Swapped! Should be debit 1000
    ]
    repaired_txns, report = reconcile_and_repair_transactions(txns, opening_balance=10000.0, closing_balance=8500.0)
    assert repaired_txns[1].validation_status == "Repaired"
    assert repaired_txns[1].debit == 1000.0
    assert repaired_txns[1].credit is None
    assert report.repaired_rows == 1
    assert report.is_reconciled is True


def test_validator_auto_repair_misread_digit():
    # In row 2, debit of 4000.0 was OCR misread as 400.0
    txns = [
        Transaction(date="2024-01-01", description="Txn 1", debit=1000.0, balance=9000.0),
        Transaction(date="2024-01-02", description="Txn 2", debit=400.0, balance=5000.0),  # Misread 4000 as 400
    ]
    repaired_txns, report = reconcile_and_repair_transactions(txns, opening_balance=10000.0, closing_balance=5000.0)
    assert repaired_txns[1].validation_status == "Repaired"
    assert repaired_txns[1].debit == 4000.0
    assert report.repaired_rows == 1
    assert report.is_reconciled is True
