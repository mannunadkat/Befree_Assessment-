"""Tests for CSV and Excel Export."""

import os
from core.models import AccountDetails, Transaction, ValidationReport
from core.exporter import export_to_csv, export_to_excel


def test_export_csv_and_excel(tmp_path):
    acc = AccountDetails(
        account_holder_name="Arjun Mehta",
        account_number="50100293847561",
        bank_name="HDFC Bank",
        opening_balance=100000.0,
        closing_balance=182210.50
    )
    txns = [
        Transaction(
            date="2024-01-02",
            description="Swiggy Order Food",
            debit=489.0,
            balance=99511.0,
            category="Food & Dining",
            category_confidence=0.95,
            classification_source="rule",
            source_file="test.pdf",
            page=1
        ),
        Transaction(
            date="2024-01-10",
            description="Salary Credit",
            credit=85000.0,
            balance=184511.0,
            category="Salary/Income",
            category_confidence=0.98,
            classification_source="rule",
            source_file="test.pdf",
            page=1
        )
    ]
    val = ValidationReport(
        total_rows=2,
        ok_rows=2,
        opening_balance=100000.0,
        closing_balance=184511.0,
        is_reconciled=True
    )

    csv_path = str(tmp_path / "export.csv")
    csv_bytes = export_to_csv(txns, csv_path)
    assert len(csv_bytes) > 50
    assert os.path.exists(csv_path)

    xlsx_path = str(tmp_path / "export.xlsx")
    xlsx_bytes = export_to_excel(acc, txns, val, xlsx_path)
    assert len(xlsx_bytes) > 1000
    assert os.path.exists(xlsx_path)
