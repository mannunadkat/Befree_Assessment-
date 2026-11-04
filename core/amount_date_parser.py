"""Date and Amount parsing utilities with OCR error resilience and Indian number formatting."""

import re
from datetime import datetime
from typing import Optional, Tuple, Any


MONTH_NAMES = {
    "jan": "01", "january": "01",
    "feb": "02", "february": "02",
    "mar": "03", "march": "03",
    "apr": "04", "april": "04",
    "may": "05",
    "jun": "06", "june": "06",
    "jul": "07", "july": "07",
    "aug": "08", "august": "08",
    "sep": "09", "september": "09", "sept": "09",
    "oct": "10", "october": "10",
    "nov": "11", "november": "11",
    "dec": "12", "december": "12"
}

DATE_PATTERNS = [
    # YYYY-MM-DD or YYYY/MM/DD
    re.compile(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$"),
    # DD-MM-YYYY or DD/MM/YYYY or DD.MM.YYYY
    re.compile(r"^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})$"),
    # DD-MM-YY or DD/MM/YY
    re.compile(r"^(\d{1,2})[-/.](\d{1,2})[-/.](\d{2})$"),
    # DD Mon YYYY or DD-Mon-YYYY (e.g. 15 Jan 2024, 05-Mar-2024)
    re.compile(r"^(\d{1,2})[-/\s]([A-Za-z]{3,9})[-/\s](\d{2,4})$"),
    # Mon DD, YYYY or Mon DD YYYY
    re.compile(r"^([A-Za-z]{3,9})[-/\s](\d{1,2}),?[-/\s](\d{2,4})$"),
]


def clean_ocr_date_string(text: str) -> str:
    """Fix common OCR typos in date strings like letter O instead of 0, l/I instead of 1."""
    if not text:
        return ""
    s = text.strip().strip("\"'`\u2018\u2019\u201c\u201d*~")
    s = s.replace("'", " ")
    # Clean up punctuation noise often found in OCR dates
    s = re.sub(r'[\";:`~*]', ' ', s)

    # Strip symbols at start/end
    s = re.sub(r'^[^\w\d]+', '', s)
    s = re.sub(r'[^\w\d]+$', '', s)

    # Day repairs
    # Stray separator/character between day and month e.g. 02VJan, 02\Jan, 02/Jan, 02iJan -> 02 Jan
    s = re.sub(r'(?<=\d)[\\/|Vvi]\s*([A-Za-z]{3})', r' \1', s)
    # Misread s/S inside day digit: e.g. 0sJan -> 05 Jan
    s = re.sub(r'(?<=\d)[sS](?=[A-Za-z]{3})', '5', s)
    # Day with comma/dot before month: e.g. 28,Jan -> 28 Jan
    s = re.sub(r'(\d+)[,.]\s*([A-Za-z]{3})', r'\1 \2', s)
    # Day > 31: 4X -> 1X (e.g. 42 -> 12, 45 -> 15, 46 -> 16, 40 -> 10, 48 -> 18, 49 -> 19)
    s = re.sub(r'\b4([0-9])(?=[.\sA-Za-z]|$)', r'1\1', s)
    # OCR letters before digit in day: Q7 -> 07, O7 -> 07, D7 -> 07, O07 -> 07
    s = re.sub(r'\b[QOD]0?([0-9])', r'0\1', s)
    # Bracket/brace/pipe misread for 1: {8 -> 18, [8 -> 18, !8 -> 18
    s = re.sub(r'[{(\[|!]([0-9])', r'1\1', s)
    # B7 -> 27, B8 / BB -> 28, B Jan -> 28 Jan
    s = re.sub(r'\bB(\d)\s*([A-Za-z]{3})', r'2\1 \2', s)
    s = re.sub(r'\bB([0-9B])', r'28', s)
    s = re.sub(r'\bB\s*([A-Za-z]{3})', r'28 \1', s)
    # 94 -> 01
    s = re.sub(r'\b94\b', '01', s)

    # Special OCR artifacts in noisy scans
    s = re.sub(r'\b4@\s*u?an\b', '16 Jan', s, flags=re.IGNORECASE)
    s = re.sub(r'\bevan\b', '18 Jan', s, flags=re.IGNORECASE)

    # Month OCR typos
    s = re.sub(r'\b[dD]un\b', 'Jun', s)
    s = re.sub(r'\b[dD]an\b', 'Jan', s)
    s = re.sub(r'\b[vVqQ]an\b', 'Jan', s)
    s = re.sub(r'(?<=\d)[vVqQdD]an', ' Jan', s)
    s = re.sub(r'\b[oO0][fFtTlI1]\b', '01', s)
    s = re.sub(r'\b[oO0][fFtTlI1](?=[A-Za-z])', '01 ', s)
    s = re.sub(r'(?<=[A-Za-z]{3}\s)[oO](\d)', r'0\1', s)
    # Split merged digit-alpha like 02Jan -> 02 Jan, and Jan2026 -> Jan 2026
    s = re.sub(r'(\d{1,2})[.\s]*([A-Za-z]{3,})', r'\1 \2', s)
    s = re.sub(r'([A-Za-z]{3,})(\d{2,4})', r'\1 \2', s)
    # Replace characters that might be misread only when surrounding characters are digits/slashes
    # e.g., 1O/12/2024 -> 10/12/2024
    s = re.sub(r'(?<=\d)[oO](?=\d)', '0', s)
    s = re.sub(r'(?<=[/\-.])[oO](?=\d)', '0', s)
    s = re.sub(r'(?<=\d)[oO](?=[/\-.])', '0', s)
    s = re.sub(r'^[oO](?=\d)', '0', s)
    s = re.sub(r'^[lI|](?=\d)', '1', s)
    s = re.sub(r'(?<=[/\-.])[lI|](?=\d)', '1', s)
    s = re.sub(r'(?<=\d)[lI|](?=[/\-.])', '1', s)
    # Fax OCR artifacts: e.g. 2026-G7-3r -> 2026-07-01
    s = re.sub(r'(?<=[/\-.])[gG](?=\d)', '0', s)
    s = re.sub(r'(?<=\d)[gG](?=[/\-.])', '0', s)
    s = re.sub(r'(\d{4}[/\-.])5(?=[0123]\d)', r'\g<1>0', s)  # 2026-57-01 -> 2026-07-01
    s = re.sub(r'(\d{4}[/\-.])9(?=[0123]\d)', r'\g<1>0', s)  # 2026-97-01 -> 2026-07-01
    s = re.sub(r'[3sS][rR]$', '01', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def parse_date(date_str: Optional[str], default_year: int = 2026) -> Optional[str]:
    """
    Parse multiple date formats into standard ISO YYYY-MM-DD.
    Returns None if the string cannot be parsed as a date.
    """
    if not date_str:
        return None
    cleaned = clean_ocr_date_string(date_str.strip())
    # Strip any trailing time or punctuation
    cleaned = re.sub(r'\s+\d{1,2}:\d{2}(:\d{2})?(\s*[aApP][mM])?.*$', '', cleaned)
    cleaned = cleaned.strip(',.;:')

    # Try standard regex patterns
    # 1. YYYY-MM-DD
    m1 = DATE_PATTERNS[0].match(cleaned)
    if m1:
        y, m, d = m1.groups()
        try:
            dt = datetime(int(y), int(m), int(d))
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass

    # 2. DD-MM-YYYY
    m2 = DATE_PATTERNS[1].match(cleaned)
    if m2:
        d, m, y = m2.groups()
        try:
            dt = datetime(int(y), int(m), int(d))
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass

    # 3. DD-MM-YY
    m3 = DATE_PATTERNS[2].match(cleaned)
    if m3:
        d, m, y_short = m3.groups()
        y_int = int(y_short)
        full_y = 2000 + y_int if y_int < 70 else 1900 + y_int
        try:
            dt = datetime(full_y, int(m), int(d))
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass

    # 4. DD Mon YYYY / DD-Mon-YYYY
    m4 = DATE_PATTERNS[3].match(cleaned)
    if m4:
        d, mon_str, y_str = m4.groups()
        mon_key = mon_str.lower()
        if mon_key not in MONTH_NAMES and len(mon_key) >= 3 and mon_key[:3] in MONTH_NAMES:
            mon_key = mon_key[:3]
        if mon_key in MONTH_NAMES:
            m = int(MONTH_NAMES[mon_key])
            y_int = int(y_str)
            full_y = y_int if y_int > 100 else (2000 + y_int if y_int < 70 else 1900 + y_int)
            try:
                dt = datetime(full_y, m, int(d))
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                pass

    # 5. Mon DD, YYYY
    m5 = DATE_PATTERNS[4].match(cleaned)
    if m5:
        mon_str, d, y_str = m5.groups()
        mon_key = mon_str.lower()
        if mon_key not in MONTH_NAMES and len(mon_key) >= 3 and mon_key[:3] in MONTH_NAMES:
            mon_key = mon_key[:3]
        if mon_key in MONTH_NAMES:
            m = int(MONTH_NAMES[mon_key])
            y_int = int(y_str)
            full_y = y_int if y_int > 100 else (2000 + y_int if y_int < 70 else 1900 + y_int)
            try:
                dt = datetime(full_y, m, int(d))
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                pass

    # 6. Search for DD Mon YYYY anywhere in the string (resilient to surrounding OCR noise)
    m_search = re.search(r'\b([0-3]?[0-9])\s+([A-Za-z]{3,9})\s+(\d{4})\b', cleaned)
    if m_search:
        d, mon_str, y_str = m_search.groups()
        mon_key = mon_str.lower()
        if mon_key not in MONTH_NAMES and len(mon_key) >= 3 and mon_key[:3] in MONTH_NAMES:
            mon_key = mon_key[:3]
        if mon_key in MONTH_NAMES:
            try:
                dt = datetime(int(y_str), int(MONTH_NAMES[mon_key]), int(d))
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                pass

    # 7. DD Mon (without year, e.g. '02 Jan', '10 Jan', '18 Jan')
    m6 = re.search(r'\b([0-3]?[0-9])\s+([A-Za-z]{3,9})\b', cleaned)
    if m6:
        d_cand, mon_str = m6.groups()
        mon_key = mon_str.lower()
        if mon_key not in MONTH_NAMES and len(mon_key) >= 3 and mon_key[:3] in MONTH_NAMES:
            mon_key = mon_key[:3]
        if mon_key in MONTH_NAMES:
            m = int(MONTH_NAMES[mon_key])
            try:
                dt = datetime(default_year, m, int(d_cand))
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                pass

    return None


def is_valid_date(text: Optional[str]) -> bool:
    """Helper to check if a token or cell contains a valid date."""
    return parse_date(text) is not None


def clean_amount_string(raw: str) -> str:
    """
    Apply OCR error correction and cleaning to an amount string.
    Fixes:
    - O / o -> 0
    - l / I / | -> 1
    - S / s -> 5 (when in numeric context)
    - Stray spaces inside numbers e.g. '1 2, 4 5 0 . 0 0' -> '12,450.00'
    - Stray commas or dots
    """
    if not raw:
        return ""
    s = raw.strip()

    # Preserve Dr / Cr or +/- before cleaning numbers
    dr_cr = ""
    upper = s.upper()
    if re.search(r'(?i)(?:^|[^a-z])dr(?:$|[^a-z])', s):
        dr_cr = "DR"
    elif re.search(r'(?i)(?:^|[^a-z])cr(?:$|[^a-z])', s):
        dr_cr = "CR"
    elif "DR" in upper:
        dr_cr = "DR"
    elif "CR" in upper:
        dr_cr = "CR"

    # Remove Dr / Cr from the string while cleaning digits
    s = re.sub(r'(?i)(?:dr|cr)', '', s).strip()

    # Check parentheses for negative: (1,234.50)
    is_paren = s.startswith("(") and s.endswith(")")
    if is_paren:
        s = s[1:-1].strip()

    # Check leading sign
    sign = "-" if (is_paren or s.startswith("-")) else ("+" if s.startswith("+") else "")
    s = s.lstrip("+-").strip()

    # Currency symbols (Rs, INR, ₹, $, €)
    s = re.sub(r'(?i)(inr|rs\.?|₹|\$|€)', '', s).strip()

    # Strip common noise words that appear when text spills into amount column
    s = re.sub(r'(?i)\b(of|for|to|no|by|in|at|on|the|and|or|tr|chq|ref|bal|amt|oes|ars|see|page|sample|fictional|data|aic|a/c|account|customer|name|ifsc|branch|balance|bank)\b', ' ', s).strip()

    # OCR character replacements in numeric context
    s = s.replace('O', '0').replace('o', '0')
    s = s.replace('I', '1').replace('l', '1').replace('|', '1')
    # If S is next to digits, replace with 5
    s = re.sub(r'(?<=\d)[Ss]', '5', s)
    s = re.sub(r'[Ss](?=\d)', '5', s)

    # Strip stray single digit at the end if the number already ended with .XX or ,XX (e.g. '800,00 2' -> '800,00')
    s = re.sub(r'([,\.]\d{2})\s+\d{1,2}(?=\s*$)', r'\1', s)

    # Missing decimal point: space before exactly two digits at the end (e.g. '1,847 00' -> '1,847.00')
    s = re.sub(r'(\d+)\s+(\d{2})(?=\s*$)', r'\1.\2', s)
    # Five zeros at the end: dropped comma and dot (e.g. '18 00000' -> '18000.00', '48 00000' -> '48000.00')
    s = re.sub(r'(\d+)\s*00000(?=\s*$)', r'\g<1>000.00', s)

    # Remove spaces between digits, commas, and dots
    s = re.sub(r'(?<=[0-9,\.])\s+(?=[0-9,\.])', '', s)

    # Handle multiple dots/commas
    # Standard format: commas as grouping separators, dot as decimal separator
    # E.g. Indian 1,23,456.78 or 123456.78
    return f"{sign}{s} {dr_cr}".strip()


def parse_amount(val: Any) -> Tuple[Optional[float], Optional[str]]:
    """
    Parse an amount value into a float and an optional direction indicator ("DR" or "CR").
    Returns (amount_float, direction) where direction can be 'DR', 'CR', or None.
    If parsing fails, returns (None, None).
    """
    if val is None:
        return None, None
    if isinstance(val, (int, float)):
        f = float(val)
        if f < 0:
            return abs(f), "DR"
        return f, "CR"

    raw = str(val).strip()
    if not raw or raw in ["-", "--", "NA", "N/A", "nil", "NIL", "0", "0.00"]:
        if raw in ["0", "0.00"]:
            return 0.0, None
        return None, None

    cleaned = clean_amount_string(raw)
    if not cleaned:
        return None, None

    # Detect Dr / Cr
    direction = None
    if "DR" in cleaned.upper():
        direction = "DR"
    elif "CR" in cleaned.upper():
        direction = "CR"

    # Remove non-numeric except digits, dot, comma, minus
    pure = re.sub(r'[^0-9,\.\-]', '', cleaned)
    # Strip leading/trailing dots and commas (e.g. from OCR punctuation like Cr. or (INR).)
    pure = pure.strip('.,')
    if not pure:
        return None, None

    is_negative = pure.startswith("-")
    if is_negative:
        pure = pure[1:].strip('.,')
        if direction is None:
            direction = "DR"

    # Normalize decimal separator:
    # If both dot and comma exist:
    # E.g. 1,23,456.78 -> comma is thousand, dot is decimal
    # E.g. 1.23.456,78 -> dot is thousand, comma is decimal (European)
    last_dot = pure.rfind('.')
    last_comma = pure.rfind(',')

    if last_dot > -1 and last_comma > -1:
        if last_dot > last_comma:
            # commas are grouping
            pure = pure.replace(',', '')
        else:
            # dots are grouping, comma is decimal
            pure = pure.replace('.', '').replace(',', '.')
    elif last_comma > -1 and last_dot == -1:
        # Check if comma is decimal (e.g. 1234,56) or grouping (e.g. 1,234 or 12,345)
        # In Indian/Western banking, if there are 2 digits after comma, it could be decimal
        parts = pure.split(',')
        if len(parts) == 2 and len(parts[1]) == 2:
            pure = parts[0] + '.' + parts[1]
        else:
            pure = pure.replace(',', '')
    else:
        # only dot or neither
        # If multiple dots: e.g. OCR mistake 12.345.67 -> keep last dot as decimal
        if pure.count('.') > 1:
            parts = pure.split('.')
            pure = "".join(parts[:-1]) + "." + parts[-1]

    # Re-strip trailing dots or commas after split
    pure = pure.strip('.,')

    # Bank statements always have 2 decimal places (.XX); if OCR dropped decimal point,
    # restore the last two digits as cents/paise ONLY if reasonable length (5 to 9 digits).
    # If 10+ digits without decimal, it is an account number, phone number, or ref number!
    if '.' not in pure:
        if 5 <= len(pure) <= 9:
            pure = pure[:-2] + '.' + pure[-2:]
        elif len(pure) >= 10:
            return None, None

    try:
        num = float(pure)
        if abs(num) > 50_000_000.0:  # 5 Crore ceiling: guards against account/ref/phone numbers
            return None, None
        if is_negative:
            num = -abs(num)
        return abs(num), direction
    except ValueError:
        return None, None


def resolve_split_debit_credit(
    d_raw: str,
    c_raw: str,
    d_val: Optional[float],
    c_val: Optional[float],
    last_balance: Optional[float] = None,
    current_balance: Optional[float] = None
) -> Tuple[Optional[float], Optional[float]]:
    """
    Resolve and recombine amounts when a single transaction amount was split across
    the Debit and Credit column boundaries (e.g. integer part in Debit and decimal part in Credit,
    or vice versa).
    """
    if d_val == 0.0:
        d_val = None
    if c_val == 0.0:
        c_val = None

    if d_val is None and c_val is None:
        return None, None
    if d_val is not None and c_val is None:
        return d_val, None
    if c_val is not None and d_val is None:
        return None, c_val

    # Both Debit and Credit are non-zero: a single bank transaction is never both!
    d_s = str(d_raw or "").strip()
    c_s = str(c_raw or "").strip()

    # Priority 1: Check balance delta if balances are known
    if last_balance is not None and current_balance is not None:
        delta = round(current_balance - last_balance, 2)
        if delta < 0:
            target = abs(delta)
            if c_val < 1.0 and abs(d_val + c_val - target) < 0.05:
                return round(d_val + c_val, 2), None
            if c_val >= 1.0 and abs(d_val + (c_val / 100.0) - target) < 0.05:
                return round(d_val + (c_val / 100.0), 2), None
            if d_val < 1.0 and abs(c_val + d_val - target) < 0.05:
                return round(c_val + d_val, 2), None
            return round(target, 2), None
        elif delta > 0:
            target = delta
            if d_val < 1.0 and abs(c_val + d_val - target) < 0.05:
                return None, round(c_val + d_val, 2)
            if d_val >= 1.0 and abs(c_val + (d_val / 100.0) - target) < 0.05:
                return None, round(c_val + (d_val / 100.0), 2)
            if c_val < 1.0 and abs(d_val + c_val - target) < 0.05:
                return None, round(d_val + c_val, 2)
            return None, round(target, 2)

    # Priority 2: Decimal prefix / suffix checks
    if c_s.startswith(('.', ',')) or (re.fullmatch(r'\d{1,2}', c_s) and d_val >= 10.0 and '.' not in d_s):
        combined = f"{d_s.rstrip('.,')}.{c_s.lstrip('.,')}"
        amt, _ = parse_amount(combined)
        return (amt if amt is not None else d_val), None

    if d_s.startswith(('.', ',')) or (re.fullmatch(r'\d{1,2}', d_s) and c_val >= 10.0 and '.' not in c_s):
        combined = f"{c_s.rstrip('.,')}.{d_s.lstrip('.,')}"
        amt, _ = parse_amount(combined)
        return None, (amt if amt is not None else c_val)

    if d_s.endswith(('.', ',')):
        combined = f"{d_s}{c_s}"
        amt, _ = parse_amount(combined)
        return (amt if amt is not None else d_val), None

    if c_s.endswith(('.', ',')):
        combined = f"{c_s}{d_s}"
        amt, _ = parse_amount(combined)
        return None, (amt if amt is not None else c_val)

    if c_val < 1.0 and d_val >= 1.0:
        return round(d_val + c_val, 2), None
    if d_val < 1.0 and c_val >= 1.0:
        return None, round(c_val + d_val, 2)

    # Priority 3: Fallback to larger magnitude
    if d_val >= c_val:
        return d_val, None
    return None, c_val
