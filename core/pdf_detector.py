"""PDF type detector: classifies pages and documents as text, scanned, or hybrid."""

import os
from typing import Dict, Any, Tuple, List, Optional
import pymupdf


def classify_document_nature(text: str) -> str:
    """
    Classify whether document is a bank/credit-card statement, invoice, or other document.
    Returns: "bank_statement" | "credit_card" | "invoice" | "unknown"
    """
    if not text:
        return "unknown"
    lower = text.lower()
    
    invoice_markers = [
        "tax invoice", "invoice no", "bill to:", "bill to ", "invoice date",
        "item qty rate", "total amount due for invoice", "sub total", "tax rate"
    ]
    statement_markers = [
        "statement of account", "account statement", "detailed statement", "passbook",
        "account number", "account no", "acct no", "ifsc", "micr", "branch",
        "savings account", "current account", "withdrawal", "deposit", "credit card statement",
        "card number", "payment due date"
    ]
    
    inv_score = sum(1 for m in invoice_markers if m in lower)
    stmt_score = sum(1 for m in statement_markers if m in lower)
    
    if "credit card statement" in lower or ("card number" in lower and "payment due date" in lower):
        return "credit_card"
    if inv_score >= 2 and stmt_score < 2:
        return "invoice"
    if stmt_score >= 1:
        return "bank_statement"
    return "unknown"


def detect_pdf_type(file_path: str, password: str = "") -> Dict[str, Any]:
    """
    Detects whether a PDF is text-based, scanned (image-based), hybrid, or invalid/non-statement.
    Returns:
    {
        "is_encrypted": bool,
        "password_required": bool,
        "doc_type": "text" | "scanned" | "hybrid" | "empty" | "invalid",
        "doc_nature": "bank_statement" | "credit_card" | "invoice" | "unknown",
        "page_count": int,
        "pages": {page_num: "text" | "scanned"},
        "error": Optional[str]
    }
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"PDF file not found: {file_path}")

    # Check magic bytes to reject non-PDF files (e.g. renamed PNGs)
    try:
        with open(file_path, "rb") as f:
            header = f.read(5)
            if not header.startswith(b"%PDF-"):
                return {
                    "is_encrypted": False,
                    "password_required": False,
                    "doc_type": "invalid",
                    "doc_nature": "unknown",
                    "page_count": 0,
                    "pages": {},
                    "error": "Invalid file format: Not a valid PDF document (magic bytes mismatch)."
                }
    except Exception as e:
        return {
            "error": str(e),
            "is_encrypted": False,
            "password_required": False,
            "doc_type": "invalid",
            "doc_nature": "unknown",
            "page_count": 0,
            "pages": {}
        }

    try:
        doc = pymupdf.open(file_path)
    except Exception as e:
        return {
            "error": str(e),
            "is_encrypted": False,
            "password_required": False,
            "doc_type": "unknown",
            "doc_nature": "unknown",
            "page_count": 0,
            "pages": {}
        }

    if doc.is_encrypted:
        if password:
            ok = doc.authenticate(password)
            if not ok:
                doc.close()
                return {
                    "is_encrypted": True,
                    "password_required": True,
                    "error": "Invalid password provided",
                    "doc_type": "unknown",
                    "doc_nature": "unknown",
                    "page_count": 0,
                    "pages": {}
                }
        else:
            doc.close()
            return {
                "is_encrypted": True,
                "password_required": True,
                "doc_type": "unknown",
                "doc_nature": "unknown",
                "page_count": 0,
                "pages": {}
            }

    page_count = len(doc)
    if page_count == 0:
        doc.close()
        return {
            "is_encrypted": False,
            "password_required": False,
            "doc_type": "empty",
            "doc_nature": "unknown",
            "page_count": 0,
            "pages": {},
            "error": "Empty PDF: Document contains 0 pages."
        }

    page_types: Dict[int, str] = {}
    text_pages = 0
    scanned_pages = 0
    all_sample_text: List[str] = []
    total_words_doc = 0

    for i in range(page_count):
        page = doc[i]
        # Count words and text length
        text = page.get_text("text").strip()
        if i < 3 and text:
            all_sample_text.append(text)
        words = text.split()
        word_count = len(words)
        total_words_doc += word_count

        # Check images
        images = page.get_images()
        has_large_image = False
        page_area = page.rect.width * page.rect.height

        for img in images:
            try:
                rects = page.get_image_rects(img[0])
                for r in rects:
                    if (r.width * r.height) / page_area > 0.40:
                        has_large_image = True
                        break
            except Exception:
                pass

        # Check for truly blank/empty page (no text, no images, no drawings)
        is_page_blank = (word_count == 0 and len(images) == 0 and len(page.get_drawings()) == 0)

        # If page has very few extractable words (< 20) and contains images or empty text
        if is_page_blank:
            page_type = "empty"
        elif word_count < 20:
            page_type = "scanned"
            scanned_pages += 1
        elif has_large_image and word_count < 50:
            page_type = "scanned"
            scanned_pages += 1
        else:
            page_type = "text"
            text_pages += 1

        page_types[i + 1] = page_type

    doc.close()

    full_sample = "\n".join(all_sample_text)
    doc_nature = classify_document_nature(full_sample)

    empty_pages = sum(1 for pt in page_types.values() if pt == "empty")
    if empty_pages == page_count:
        doc_type = "empty"
    elif scanned_pages == 0:
        doc_type = "text"
    elif text_pages == 0:
        doc_type = "scanned"
    else:
        doc_type = "hybrid"

    error_msg = None
    if doc_nature == "invoice":
        error_msg = "Document rejected: Not a bank statement (detected Tax Invoice)."

    return {
        "is_encrypted": False,
        "password_required": False,
        "doc_type": doc_type,
        "doc_nature": doc_nature,
        "page_count": page_count,
        "pages": page_types,
        "error": error_msg
    }
