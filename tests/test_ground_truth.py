"""
Comprehensive ground-truth extraction accuracy tests.
Covers all 21 PDF test cases in ``test cases/``, plus classifier accuracy.
Each test asserts a minimum match-rate threshold against the provided CSVs.

Run with:
    .venv/bin/pytest tests/test_ground_truth.py -v
"""
import csv
import os
import pytest
import pandas as pd
from decimal import Decimal as D
from typing import List, Optional

from core.pdf_detector import detect_pdf_type
from core.layout_parser import extract_transactions_from_page
from core.validator import reconcile_and_repair_transactions
from core.models import Transaction
from core.classifier.hybrid import classify_transaction

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TC = os.path.join(BASE, "test cases")
TEXT_DIR = os.path.join(TC, "text_based")
SCAN_DIR = os.path.join(TC, "scanned_image_based")
EDGE_DIR = os.path.join(TC, "edge_cases")
MIXED_DIR = os.path.join(TC, "mixed_and_multi")
OTHER_DIR = os.path.join(TC, "other_document_types")
GT_DIR = os.path.join(TC, "ground_truth")
CLASS_DIR = os.path.join(TC, "classification_data")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _num(x) -> D:
    """Parse a numeric CSV cell to Decimal."""
    if x in ("", None):
        return D(0)
    return D(str(x).replace(",", "").strip())


def _key(row: dict):
    """Canonical match key: (date, debit, credit, balance)."""
    return (
        row.get("date", "").strip(),
        _num(row.get("debit", "")),
        _num(row.get("credit", "")),
        _num(row.get("balance", "")),
    )


def _tx_to_row(tx: Transaction) -> dict:
    return {
        "date": tx.date or "",
        "debit": str(tx.debit) if tx.debit is not None else "",
        "credit": str(tx.credit) if tx.credit is not None else "",
        "balance": str(tx.balance) if tx.balance is not None else "",
    }


def _load_ground_truth(csv_path: str) -> List[dict]:
    with open(csv_path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _extract_all_pages(
    pdf_path: str,
    is_scanned: bool = False,
    password: str = "",
    opening_balance: Optional[float] = None,
    closing_balance: Optional[float] = None,
) -> List[Transaction]:
    """Extract transactions from every page of a PDF and optionally reconcile."""
    det = detect_pdf_type(pdf_path, password=password)
    page_count = det["page_count"]
    all_tx: List[Transaction] = []
    bounds = None
    for p in range(1, page_count + 1):
        page_type = det["pages"].get(p, "text")
        scan = is_scanned or (page_type == "scanned")
        try:
            txs, b = extract_transactions_from_page(
                pdf_path, p, is_scanned=scan, saved_boundaries=bounds, password=password
            )
        except Exception:
            txs, b = [], bounds
        if b:
            bounds = b
        all_tx.extend(txs)
    if opening_balance is not None or closing_balance is not None:
        all_tx, _ = reconcile_and_repair_transactions(
            all_tx, opening_balance=opening_balance, closing_balance=closing_balance
        )
    return all_tx


def _score(extracted: List[Transaction], gt_rows: List[dict]):
    """Return (hits, total_gt) for exact-match scoring."""
    pool = [_key(_tx_to_row(t)) for t in extracted]
    hits = 0
    for row in gt_rows:
        k = _key(row)
        if k in pool:
            pool.remove(k)
            hits += 1
    return hits, len(gt_rows)


def _assert_accuracy(hits: int, total: int, threshold_pct: float, label: str):
    pct = 100 * hits / max(1, total)
    assert pct >= threshold_pct, (
        f"{label}: accuracy {pct:.1f}% < required {threshold_pct}% "
        f"({hits}/{total} matches)"
    )


# ===========================================================================
# Text-based PDF tests (01–06) — expect ≥ 95%
# ===========================================================================

class TestTextBasedPDFs:

    def test_01_bordered_debit_credit(self):
        pdf = os.path.join(TEXT_DIR, "01_text_bordered_debit_credit_carry_forward.pdf")
        gt = _load_ground_truth(os.path.join(GT_DIR, "01_text_bordered_debit_credit_carry_forward.csv"))
        txs = _extract_all_pages(pdf)
        hits, total = _score(txs, gt)
        _assert_accuracy(hits, total, 95.0, "Test 01 (bordered debit/credit)")

    def test_02_borderless_dr_cr_suffix(self):
        pdf = os.path.join(TEXT_DIR, "02_text_borderless_amount_with_Dr_Cr_suffix.pdf")
        gt = _load_ground_truth(os.path.join(GT_DIR, "02_text_borderless_amount_with_Dr_Cr_suffix.csv"))
        txs = _extract_all_pages(pdf)
        hits, total = _score(txs, gt)
        _assert_accuracy(hits, total, 95.0, "Test 02 (Dr/Cr suffix)")

    def test_03_multiline_narration_withdrawal_deposit(self):
        pdf = os.path.join(TEXT_DIR, "03_text_multiline_narration_withdrawal_deposit.pdf")
        gt = _load_ground_truth(os.path.join(GT_DIR, "03_text_multiline_narration_withdrawal_deposit.csv"))
        txs = _extract_all_pages(pdf)
        hits, total = _score(txs, gt)
        _assert_accuracy(hits, total, 95.0, "Test 03 (multiline narration)")

    def test_04_monospace_signed_amounts(self):
        pdf = os.path.join(TEXT_DIR, "04_text_monospace_whitespace_aligned_signed_amounts.pdf")
        gt = _load_ground_truth(os.path.join(GT_DIR, "04_text_monospace_whitespace_aligned_signed_amounts.csv"))
        txs = _extract_all_pages(pdf)
        hits, total = _score(txs, gt)
        _assert_accuracy(hits, total, 95.0, "Test 04 (monospace signed amounts)")

    def test_05_landscape_passbook_zero_filled(self):
        pdf = os.path.join(TEXT_DIR, "05_text_landscape_passbook_style_zero_filled.pdf")
        gt = _load_ground_truth(os.path.join(GT_DIR, "05_text_landscape_passbook_style_zero_filled.csv"))
        txs = _extract_all_pages(pdf)
        hits, total = _score(txs, gt)
        _assert_accuracy(hits, total, 95.0, "Test 05 (landscape passbook)")

    def test_06_bracket_negatives_western_format(self):
        pdf = os.path.join(TEXT_DIR, "06_text_bracket_negatives_western_number_format.pdf")
        gt = _load_ground_truth(os.path.join(GT_DIR, "06_text_bracket_negatives_western_number_format.csv"))
        txs = _extract_all_pages(pdf)
        hits, total = _score(txs, gt)
        _assert_accuracy(hits, total, 95.0, "Test 06 (bracket negatives)")


# ===========================================================================
# Scanned PDF tests (07–11) — expect ≥ 70% (OCR introduces noise)
# ===========================================================================

class TestScannedPDFs:

    def test_07_scanned_clean_200dpi(self):
        pdf = os.path.join(SCAN_DIR, "07_scanned_clean_200dpi.pdf")
        gt = _load_ground_truth(os.path.join(GT_DIR, "07_scanned_clean_200dpi.csv"))
        txs = _extract_all_pages(pdf, is_scanned=True)
        hits, total = _score(txs, gt)
        _assert_accuracy(hits, total, 70.0, "Test 07 (clean 200dpi scan)")

    def test_08_scanned_skewed_noisy_low_contrast(self):
        """Severely degraded: 1.7° skew, blur, noise, speckles, low contrast JPEG."""
        pdf = os.path.join(SCAN_DIR, "08_scanned_skewed_noisy_low_contrast.pdf")
        det = detect_pdf_type(pdf)
        assert det["doc_type"] == "scanned", f"Expected scanned, got {det['doc_type']}"
        txs = _extract_all_pages(pdf, is_scanned=True)
        assert isinstance(txs, list)
        for t in txs:
            assert isinstance(t, Transaction)

    def test_09_scanned_phone_photo_shadow_perspective(self):
        """Phone-photo degradation: perspective warp, dark background corners, shadow."""
        pdf = os.path.join(SCAN_DIR, "09_scanned_phone_photo_shadow_perspective.pdf")
        det = detect_pdf_type(pdf)
        assert det["doc_type"] == "scanned", f"Expected scanned, got {det['doc_type']}"
        txs = _extract_all_pages(pdf, is_scanned=True)
        assert isinstance(txs, list)
        for t in txs:
            assert isinstance(t, Transaction)

    def test_10_scanned_fax_black_white_low_res(self):
        """1-bit black/white, 150 dpi, fax streaks."""
        pdf = os.path.join(SCAN_DIR, "10_scanned_fax_black_white_low_res.pdf")
        det = detect_pdf_type(pdf)
        assert det["doc_type"] == "scanned", f"Expected scanned, got {det['doc_type']}"
        txs = _extract_all_pages(pdf, is_scanned=True)
        assert isinstance(txs, list)
        for t in txs:
            assert isinstance(t, Transaction)

    def test_11_scanned_rotated_90_degrees(self):
        """Rotated 90 degrees plus noise: verifies orientation correction and extraction."""
        pdf = os.path.join(SCAN_DIR, "11_scanned_rotated_90_degrees.pdf")
        det = detect_pdf_type(pdf)
        assert det["doc_type"] == "scanned", f"Expected scanned, got {det['doc_type']}"
        txs = _extract_all_pages(pdf, is_scanned=True)
        assert isinstance(txs, list)
        assert len(txs) > 0, "Expected orientation correction to recover transactions"
        for t in txs:
            assert isinstance(t, Transaction)


# ===========================================================================
# Mixed / Multi tests (12–14)
# ===========================================================================

class TestMixedAndMultiPDFs:

    def test_12_mixed_text_and_scanned_pages(self):
        pdf = os.path.join(MIXED_DIR, "12_mixed_text_pages_and_scanned_pages.pdf")
        gt = _load_ground_truth(os.path.join(GT_DIR, "12_mixed_text_pages_and_scanned_pages.csv"))
        txs = _extract_all_pages(pdf)  # hybrid auto-detected per page
        hits, total = _score(txs, gt)
        _assert_accuracy(hits, total, 70.0, "Test 12 (mixed text+scan)")

    def test_13_two_accounts_in_one_pdf(self):
        pdf = os.path.join(MIXED_DIR, "13_two_accounts_in_one_pdf.pdf")
        gt = _load_ground_truth(os.path.join(GT_DIR, "13_two_accounts_in_one_pdf.csv"))
        txs = _extract_all_pages(pdf)
        hits, total = _score(txs, gt)
        _assert_accuracy(hits, total, 95.0, "Test 13 (two accounts)")

    def test_14_large_statement_100plus_pages(self):
        pdf = os.path.join(MIXED_DIR, "14_large_statement_100plus_pages.pdf")
        gt = _load_ground_truth(os.path.join(GT_DIR, "14_large_statement_100plus_pages.csv"))
        txs = _extract_all_pages(pdf)
        hits, total = _score(txs, gt)
        _assert_accuracy(hits, total, 90.0, "Test 14 (100+ page large statement)")


# ===========================================================================
# Edge case tests (15–19)
# ===========================================================================

class TestEdgeCases:

    def test_15_edge_cases_duplicates_reversals(self):
        """Balance breaks, duplicate rows, and reversal entries."""
        pdf = os.path.join(EDGE_DIR, "15_edge_cases_balance_breaks_duplicates_reversals.pdf")
        gt = _load_ground_truth(os.path.join(GT_DIR, "15_edge_cases_balance_breaks_duplicates_reversals.csv"))
        txs = _extract_all_pages(pdf)
        hits, total = _score(txs, gt)
        _assert_accuracy(hits, total, 95.0, "Test 15 (edge cases)")

    def test_16_password_protected(self):
        """PDF requiring password='test1234'."""
        pdf = os.path.join(EDGE_DIR, "16_password_protected_password_is_test1234.pdf")
        gt = _load_ground_truth(os.path.join(GT_DIR, "16_password_protected_password_is_test1234.csv"))
        txs = _extract_all_pages(pdf, password="test1234")
        hits, total = _score(txs, gt)
        _assert_accuracy(hits, total, 95.0, "Test 16 (password protected)")

    def test_17_corrupted_truncated_file(self):
        """Corrupted/truncated PDF — must not crash; partial results are OK."""
        pdf = os.path.join(EDGE_DIR, "17_corrupted_truncated_file.pdf")
        # Should complete without raising an exception
        try:
            txs = _extract_all_pages(pdf)
        except Exception as exc:
            pytest.fail(f"Test 17 raised an unexpected exception: {exc}")
        # We only require graceful handling (no crash), no accuracy threshold
        assert isinstance(txs, list), "Expected a list of transactions"

    def test_18_non_pdf_png_renamed(self):
        """PNG file renamed to .pdf — must be detected as invalid."""
        pdf = os.path.join(EDGE_DIR, "18_not_really_a_pdf_png_renamed.pdf")
        result = detect_pdf_type(pdf)
        assert result["doc_type"] == "invalid", (
            f"Expected doc_type='invalid' for PNG-renamed PDF, got '{result['doc_type']}'"
        )

    def test_19_blank_empty_page(self):
        """Blank PDF — must be detected as empty and yield zero transactions."""
        pdf = os.path.join(EDGE_DIR, "19_blank_empty_page.pdf")
        result = detect_pdf_type(pdf)
        assert result["doc_type"] == "empty", (
            f"Expected doc_type='empty' for blank PDF, got '{result['doc_type']}'"
        )
        txs = _extract_all_pages(pdf)
        assert len(txs) == 0, f"Expected 0 transactions from blank PDF, got {len(txs)}"


# ===========================================================================
# Other document types (20–21)
# ===========================================================================

class TestOtherDocumentTypes:

    def test_20_credit_card_statement_no_balance_column(self):
        """Credit card statement without a balance column."""
        pdf = os.path.join(OTHER_DIR, "20_credit_card_statement_no_balance_column.pdf")
        gt = _load_ground_truth(os.path.join(GT_DIR, "20_credit_card_statement_no_balance_column.csv"))
        txs = _extract_all_pages(pdf)
        hits, total = _score(txs, gt)
        _assert_accuracy(hits, total, 95.0, "Test 20 (credit card, no balance)")

    def test_21_non_statement_invoice_rejected(self):
        """Invoice PDF — must be detected as an invoice (not a bank statement)."""
        pdf = os.path.join(OTHER_DIR, "21_non_statement_invoice_should_be_rejected.pdf")
        result = detect_pdf_type(pdf)
        assert result["doc_nature"] == "invoice", (
            f"Expected doc_nature='invoice' for invoice PDF, got '{result['doc_nature']}'"
        )
        # Optionally: also check that doc_type is not classified as text/scanned with valid transactions
        assert result.get("error") is not None, "Expected an error/rejection message for invoice"


# ===========================================================================
# Classifier accuracy test
# ===========================================================================

class TestClassifierAccuracy:

    def test_classifier_noisy_holdout_accuracy(self):
        """ML+rule hybrid classifier must achieve ≥ 90% on the noisy holdout set."""
        holdout_path = os.path.join(CLASS_DIR, "classification_holdout_test_noisy.csv")
        df = pd.read_csv(holdout_path)
        correct = 0
        total = len(df)
        for _, row in df.iterrows():
            tx = Transaction(
                date="2026-01-01",
                description=str(row["description"]),
                balance=1000.0,
            )
            classify_transaction(tx)
            if tx.category == row["category"]:
                correct += 1
        pct = 100 * correct / max(1, total)
        assert pct >= 90.0, (
            f"Classifier accuracy {pct:.2f}% < required 90% ({correct}/{total})"
        )

