"""Text and geometry extractor using pdfplumber and PyMuPDF."""

import os
from typing import List, Dict, Any, Optional
import pdfplumber
import pymupdf


def extract_words_from_page(pdf_path: str, page_number: int, password: str = "") -> List[Dict[str, Any]]:
    """
    Extract all words with bounding boxes (x0, top, x1, bottom) from a PDF page.
    Page number is 1-indexed. Includes graceful PyMuPDF fallback for damaged/truncated PDFs.
    """
    words_data: List[Dict[str, Any]] = []
    try:
        with pdfplumber.open(pdf_path, password=password if password else None) as pdf:
            if page_number > len(pdf.pages):
                return words_data
            page = pdf.pages[page_number - 1]
            words = page.extract_words(
                x_tolerance=3,
                y_tolerance=3,
                keep_blank_chars=False,
                use_text_flow=True
            )
            for w in words:
                words_data.append({
                    "text": w["text"],
                    "x0": float(w["x0"]),
                    "top": float(w["top"]),
                    "x1": float(w["x1"]),
                    "bottom": float(w["bottom"]),
                    "confidence": 1.0
                })
            return words_data
    except Exception:
        # Fallback to PyMuPDF for robust handling of truncated or corrupted PDFs
        try:
            doc = pymupdf.open(pdf_path)
            if doc.is_encrypted and password:
                doc.authenticate(password)
            if page_number <= len(doc):
                page = doc[page_number - 1]
                raw_words = page.get_text("words")
                for w in raw_words:
                    words_data.append({
                        "text": w[4],
                        "x0": float(w[0]),
                        "top": float(w[1]),
                        "x1": float(w[2]),
                        "bottom": float(w[3]),
                        "confidence": 1.0
                    })
            doc.close()
        except Exception:
            pass
    return words_data


def extract_tables_from_page(pdf_path: str, page_number: int, password: str = "") -> List[List[List[Optional[str]]]]:
    """
    Extract structured tables using pdfplumber line/curve detection.
    Returns list of tables, where each table is a list of rows, each row is a list of cell strings.
    """
    tables: List[List[List[Optional[str]]]] = []
    try:
        with pdfplumber.open(pdf_path, password=password if password else None) as pdf:
            if page_number > len(pdf.pages):
                return tables
            page = pdf.pages[page_number - 1]
            extracted = page.extract_tables()
            if extracted:
                tables.extend(extracted)
    except Exception:
        pass
    return tables


def extract_full_text(pdf_path: str, password: str = "") -> str:
    """Extract plain text across all pages for account header parsing with fallback."""
    text_parts: List[str] = []
    try:
        with pdfplumber.open(pdf_path, password=password if password else None) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text_parts.append(t)
            return "\n".join(text_parts)
    except Exception:
        try:
            doc = pymupdf.open(pdf_path)
            if doc.is_encrypted and password:
                doc.authenticate(password)
            for page in doc:
                t = page.get_text()
                if t:
                    text_parts.append(t)
            doc.close()
            return "\n".join(text_parts)
        except Exception:
            return ""


def render_page_to_bytes(pdf_path: str, page_number: int, dpi: int = 150, password: str = "") -> bytes:
    """Render a PDF page to PNG image bytes for UI preview or OCR."""
    doc = pymupdf.open(pdf_path)
    if doc.is_encrypted and password:
        doc.authenticate(password)
    page = doc[page_number - 1]
    zoom = dpi / 72.0
    mat = pymupdf.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    img_bytes = pix.tobytes("png")
    doc.close()
    return img_bytes
