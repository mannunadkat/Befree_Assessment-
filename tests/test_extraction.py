"""Tests for text & scanned statement extraction across sample banks."""

import os
import json
import pytest
from core.pdf_detector import detect_pdf_type
from core.text_extractor import extract_words_from_page, extract_full_text
from core.ocr_extractor import extract_words_from_scanned_page, is_tesseract_available
from core.layout_parser import extract_transactions_from_page, cluster_words_into_rows, detect_header_row, parse_geometry_transactions
from core.account_parser import extract_account_details


SAMPLES_DIR = os.path.join(os.path.dirname(__file__), "..", "samples")


def test_sample_1_hdfc_extraction():
    pdf_path = os.path.join(SAMPLES_DIR, "sample_1_hdfc.pdf")
    gt_path = os.path.join(SAMPLES_DIR, "sample_1_hdfc.json")
    with open(gt_path) as f:
        gt = json.load(f)

    # 1. Account header extraction
    full_text = extract_full_text(pdf_path)
    acc = extract_account_details(full_text)
    assert acc.bank_name == "HDFC Bank"
    assert acc.account_number == gt["account_number"]
    assert acc.ifsc_code == gt["ifsc_code"]
    assert acc.opening_balance == gt["opening_balance"]
    assert acc.closing_balance == gt["closing_balance"]

    # 2. Table extraction
    txns, bounds = extract_transactions_from_page(pdf_path, 1)
    assert len(txns) == len(gt["transactions"])
    assert txns[0].date == "2024-01-02"
    assert txns[0].debit == 489.00
    assert txns[0].balance == 99511.00


def test_sample_2_icici_extraction():
    pdf_path = os.path.join(SAMPLES_DIR, "sample_2_icici.pdf")
    gt_path = os.path.join(SAMPLES_DIR, "sample_2_icici.json")
    with open(gt_path) as f:
        gt = json.load(f)

    full_text = extract_full_text(pdf_path)
    acc = extract_account_details(full_text)
    assert acc.bank_name == "ICICI Bank"
    assert acc.account_number == gt["account_number"]
    assert acc.ifsc_code == gt["ifsc_code"]

    txns, bounds = extract_transactions_from_page(pdf_path, 1)
    assert len(txns) == len(gt["transactions"])
    assert txns[0].debit == 420.00
    assert txns[2].credit == 92000.00


def test_sample_3_kotak_signed_amount():
    pdf_path = os.path.join(SAMPLES_DIR, "sample_3_kotak.pdf")
    gt_path = os.path.join(SAMPLES_DIR, "sample_3_kotak.json")
    with open(gt_path) as f:
        gt = json.load(f)

    txns, bounds = extract_transactions_from_page(pdf_path, 1)
    assert len(txns) == len(gt["transactions"])
    assert txns[0].debit == 2499.00
    assert txns[3].credit == 65000.00


def test_sample_4_sbi_multipage():
    pdf_path = os.path.join(SAMPLES_DIR, "sample_4_sbi_multipage.pdf")
    gt_path = os.path.join(SAMPLES_DIR, "sample_4_sbi_multipage.json")
    with open(gt_path) as f:
        gt = json.load(f)

    txns_p1, bounds_p1 = extract_transactions_from_page(pdf_path, 1)
    txns_p2, bounds_p2 = extract_transactions_from_page(pdf_path, 2, saved_boundaries=bounds_p1)

    total_txns = txns_p1 + txns_p2
    assert len(total_txns) == len(gt["transactions"])
    assert total_txns[0].debit == 25000.00
    assert total_txns[7].credit == 110000.00


def test_scanned_ocr_extraction():
    if not is_tesseract_available():
        pytest.skip("Tesseract OCR binary not found.")

    pdf_path = os.path.join(SAMPLES_DIR, "sample_1_hdfc_scanned.pdf")
    txns, bounds = extract_transactions_from_page(pdf_path, 1, is_scanned=True, dpi=200)
    assert len(txns) >= 8
