"""Tests for PDF Detector."""

import os
from core.pdf_detector import detect_pdf_type


SAMPLES_DIR = os.path.join(os.path.dirname(__file__), "..", "samples")


def test_pdf_detector_text():
    res = detect_pdf_type(os.path.join(SAMPLES_DIR, "sample_1_hdfc.pdf"))
    assert res["doc_type"] == "text"
    assert res["page_count"] == 1
    assert res["pages"][1] == "text"

    res4 = detect_pdf_type(os.path.join(SAMPLES_DIR, "sample_4_sbi_multipage.pdf"))
    assert res4["doc_type"] == "text"
    assert res4["page_count"] == 2
    assert res4["pages"][1] == "text"
    assert res4["pages"][2] == "text"


def test_pdf_detector_scanned():
    res = detect_pdf_type(os.path.join(SAMPLES_DIR, "sample_1_hdfc_scanned.pdf"))
    assert res["doc_type"] == "scanned"
    assert res["pages"][1] == "scanned"
