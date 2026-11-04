"""OCR extractor with image preprocessing and Tesseract integration."""

import os
import shutil
from typing import List, Dict, Any, Tuple, Optional
import numpy as np
try:
    import cv2
except ImportError:
    cv2 = None
import pymupdf
import pytesseract


def is_tesseract_available() -> bool:
    """Check if tesseract binary and cv2 are accessible."""
    if cv2 is None:
        return False
    # Check PATH first
    if shutil.which("tesseract"):
        return True
    # Common macOS / Linux paths
    common_paths = [
        "/opt/homebrew/bin/tesseract",
        "/usr/local/bin/tesseract",
        "/usr/bin/tesseract",
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"
    ]
    for p in common_paths:
        if os.path.exists(p):
            pytesseract.pytesseract.tesseract_cmd = p
            return True
    return False


def get_tesseract_install_instructions() -> Dict[str, str]:
    """Return platform-specific instructions for installing Tesseract OCR."""
    return {
        "macOS": "Run 'brew install tesseract' via Homebrew.",
        "Linux": "Run 'sudo apt-get install tesseract-ocr' (Ubuntu/Debian) or 'sudo yum install tesseract' (CentOS/RHEL).",
        "Windows": "Download installer from https://github.com/UB-Mannheim/tesseract/wiki or run 'winget install UB-Mannheim.TesseractOCR'."
    }


import re


def find_projection_deskew_angle(gray: np.ndarray, max_angle: float = 4.0) -> float:
    """Find skew angle using maximum variance of horizontal projection profile."""
    try:
        h, w = gray.shape[:2]
        scale = min(1.0, 1000.0 / max(h, w))
        if scale < 1.0:
            small = cv2.resize(gray, (int(w * scale), int(h * scale)))
        else:
            small = gray

        thresh = cv2.adaptiveThreshold(small, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 25, 10)
        sh, sw = thresh.shape[:2]
        cx, cy = sw / 2.0, sh / 2.0

        def score(a: float) -> float:
            M = cv2.getRotationMatrix2D((cx, cy), a, 1.0)
            rot = cv2.warpAffine(thresh, M, (sw, sh), flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
            return float(np.var(np.sum(rot, axis=1)))

        best_angle, best_var = 0.0, 0.0
        for a in np.arange(-max_angle, max_angle, 0.25):
            v = score(a)
            if v > best_var:
                best_var, best_angle = v, float(a)

        for a in np.arange(best_angle - 0.25, best_angle + 0.25, 0.05):
            v = score(a)
            if v > best_var:
                best_var, best_angle = v, float(a)

        return best_angle
    except Exception:
        return 0.0


def preprocess_image_for_ocr(img_bgr: np.ndarray) -> np.ndarray:
    """
    Apply orientation correction, deskew, selective illumination flattening, and contrast enhancement.
    """
    if cv2 is None:
        return img_bgr

    # 1. Grayscale
    if len(img_bgr.shape) == 3:
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    else:
        gray = img_bgr

    h, w = gray.shape[:2]

    # 2. Orientation detection & correction
    try:
        if w > h:
            # Document is landscape; rotate 90 CCW to portrait
            gray = cv2.rotate(gray, cv2.ROTATE_90_COUNTERCLOCKWISE)
            h, w = gray.shape[:2]
        else:
            osd = pytesseract.image_to_osd(gray)
            rot_m = re.search(r'Rotate:\s*(\d+)', osd)
            conf_m = re.search(r'Orientation confidence:\s*([\d.]+)', osd)
            rot_angle = int(rot_m.group(1)) if rot_m else 0
            conf_val = float(conf_m.group(1)) if conf_m else 0.0

            if rot_angle == 180 and conf_val >= 15.0:
                gray = cv2.rotate(gray, cv2.ROTATE_180)
            elif rot_angle in [90, 270] and conf_val >= 8.0:
                if rot_angle == 90:
                    gray = cv2.rotate(gray, cv2.ROTATE_90_CLOCKWISE)
                else:
                    gray = cv2.rotate(gray, cv2.ROTATE_90_COUNTERCLOCKWISE)
                h, w = gray.shape[:2]
    except Exception:
        pass

    # 3. Projection-profile Deskew
    try:
        angle = find_projection_deskew_angle(gray, max_angle=4.5)
        if 0.25 < abs(angle) < 15.0:
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            gray = cv2.warpAffine(gray, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    except Exception:
        pass

    # 4. Selective Illumination Flattening (only for phone photos / uneven dark backgrounds)
    try:
        if gray.mean() < 185:
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (45, 45))
            bg = cv2.morphologyEx(gray, cv2.MORPH_DILATE, kernel)
            gray = cv2.divide(gray, bg, scale=255)
            # Gentle unsharp mask for photo blur
            gaussian = cv2.GaussianBlur(gray, (0, 0), 1.5)
            gray = cv2.addWeighted(gray, 1.4, gaussian, -0.4, 0)
    except Exception:
        pass

    # 5. Clean linear contrast stretch (avoids CLAHE noise/ringing while clarifying faint text)
    try:
        p2, p98 = np.percentile(gray, (2, 98))
        if p98 - p2 > 20:
            gray = np.clip((gray.astype(np.float32) - p2) * 255.0 / (p98 - p2), 0, 255).astype(np.uint8)
    except Exception:
        pass

    return gray


def extract_words_from_scanned_page(
    pdf_path: str,
    page_number: int,
    dpi: int = 300,
    password: str = ""
) -> Tuple[List[Dict[str, Any]], float]:
    """
    Render PDF page to high-res image, preprocess, and run Tesseract image_to_data.
    Returns:
    (words_list, average_page_confidence)
    where words_list has elements: {"text", "x0", "top", "x1", "bottom", "confidence"}
    Coordinates are scaled back to 72 DPI PDF point coordinates for consistency.
    """
    if not is_tesseract_available():
        return [], 0.0

    doc = pymupdf.open(pdf_path)
    if doc.is_encrypted and password:
        doc.authenticate(password)

    page = doc[page_number - 1]
    scale = dpi / 72.0
    mat = pymupdf.Matrix(scale, scale)
    pix = page.get_pixmap(matrix=mat)
    img_np = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
    if pix.n == 4:
        img_np = cv2.cvtColor(img_np, cv2.COLOR_RGBA2BGR)
    elif pix.n == 1:
        img_np = cv2.cvtColor(img_np, cv2.COLOR_GRAY2BGR)

    doc.close()

    preprocessed = preprocess_image_for_ocr(img_np)

    # Run tesseract image_to_data (PSM 6 handles multi-column tabular data robustly)
    ocr_data = pytesseract.image_to_data(
        preprocessed,
        output_type=pytesseract.Output.DICT,
        config="--oem 3 --psm 6"
    )

    non_empty = [t for t in ocr_data['text'] if t.strip()]
    non_empty_lower = [t.lower().strip(".,;:|") for t in non_empty]
    has_money_header = any(k in non_empty_lower for k in ["debit", "withdrawal", "withdrawals"]) and \
                       any(k in non_empty_lower for k in ["credit", "deposit", "deposits", "balance"])

    # Fall back to PSM 3 if PSM 6 missed the table header or has low word yield
    if not has_money_header or len(non_empty) < 40:
        alt_data = pytesseract.image_to_data(
            preprocessed,
            output_type=pytesseract.Output.DICT,
            config="--oem 3 --psm 3"
        )
        alt_non_empty = [t for t in alt_data['text'] if t.strip()]
        alt_non_empty_lower = [t.lower().strip(".,;:|") for t in alt_non_empty]
        alt_has_money_header = any(k in alt_non_empty_lower for k in ["debit", "withdrawal", "withdrawals"]) and \
                               any(k in alt_non_empty_lower for k in ["credit", "deposit", "deposits", "balance"])

        if alt_has_money_header or len(alt_non_empty) > len(non_empty):
            ocr_data = alt_data

    words_data: List[Dict[str, Any]] = []
    conf_sum = 0.0
    conf_count = 0

    n_boxes = len(ocr_data['text'])
    for i in range(n_boxes):
        text = ocr_data['text'][i].strip()
        conf = float(ocr_data['conf'][i])
        if not text or conf < 0:
            continue

        # Convert image pixel coords back to 72 DPI PDF points
        x = float(ocr_data['left'][i]) / scale
        y = float(ocr_data['top'][i]) / scale
        w = float(ocr_data['width'][i]) / scale
        h = float(ocr_data['height'][i]) / scale

        words_data.append({
            "text": text,
            "x0": x,
            "top": y,
            "x1": x + w,
            "bottom": y + h,
            "confidence": conf / 100.0
        })
        conf_sum += conf
        conf_count += 1

    avg_conf = (conf_sum / (conf_count * 100.0)) if conf_count > 0 else 0.0
    return words_data, avg_conf
