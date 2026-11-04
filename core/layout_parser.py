"""Bank-agnostic transaction table layout parser and row reconstructor."""

import os
import re
import difflib
from typing import List, Dict, Any, Optional, Tuple
from core.models import Transaction
from core.amount_date_parser import parse_date, parse_amount, is_valid_date, resolve_split_debit_credit
from core.text_extractor import extract_words_from_page, extract_tables_from_page
from core.ocr_extractor import extract_words_from_scanned_page


# Canonical synonyms for column matching
SYNONYMS = {
    "date": [
        "date", "txn date", "txndate", "transaction date", "post date", "tran date",
        "trans date", "posting date", "entry date", "tranadetion date", "transéction date",
        "transction date"
    ],
    "value_date": [
        "value date", "val date", "valuedt", "value dt", "v date", "vdate"
    ],
    "description": [
        "narration", "particulars", "description", "details", "remarks",
        "transaction remarks", "transaction details", "narration/remarks",
        "particulars/narration", "transaction particulars", "transéction remarks",
        "tranadetion remarks", "remarks.", "transaction", "transactionremarks"
    ],
    "ref_no": [
        "chq/ref no", "chq / ref no", "ref no", "ref no.", "ref no./cheque no.",
        "cheque no", "cheque no.", "chq no", "reference", "ref id", "reference id",
        "txn id", "transaction id", "ref", "chq.no", "chq no.", "ref no./chq no.",
        "ref no/chq no", "ref no / chq no", "chq/ref no.", "chq/dd no"
    ],
    "debit": [
        "withdrawal", "withdrawals", "withdrawal (dr)", "withdrawal amt", "withdrawal amt.",
        "withdrawal amount", "debit", "debits", "debit (dr)", "dr", "dr.", "debit amount",
        "debit amt", "debit amt.", "dr amt", "dr amount", "withdrawals (inr)",
        "withdrawal (inr)", "debit (inr)", "debits (inr)"
    ],
    "credit": [
        "deposit", "deposits", "deposit (cr)", "deposit amt", "deposit amt.",
        "deposit amount", "credit", "credits", "credit (cr)", "cr", "cr.", "credit amount",
        "credit amt", "credit amt.", "cr amt", "cr amount", "deposits (inr)",
        "deposit (inr)", "credit (inr)", "credits (inr)"
    ],
    "amount": [
        "amount", "amount (inr)", "amount(inr)", "amount (rs.)", "amount (rs)",
        "amount(rs)", "amount in rs", "amount in inr", "txn amount", "transaction amount"
    ],
    "indicator": [
        "cr/dr", "dr/cr", "cr / dr", "dr / cr", "type", "drcr", "crdr"
    ],
    "balance": [
        "balance", "closing balance", "balance (inr)", "balance(inr)", "balance (rs.)",
        "balance (rs)", "balance(rs)", "bal", "run balance", "running balance",
        "balance amount", "closing bal", "ealanae", "ealance", "oalance", "balanoe",
        "balence", "ealanae (inr)"
    ]
}

SKIP_ROW_PATTERNS = [
    re.compile(r'\b(opening balance|balance b/f|brought forward|b/f balance)\b', re.IGNORECASE),
    re.compile(r'\b(carried forward|c/f balance|balance c/f)\b', re.IGNORECASE),
    re.compile(r'\b(total|grand total|subtotal)\b', re.IGNORECASE),
    re.compile(r'\b(total\s*debits|total\s*credits|statement\s*summary)\b', re.IGNORECASE),
    re.compile(r'\b(page \d+|statement generated on|computer generated)\b', re.IGNORECASE),
    re.compile(r'\b(customer\s*name|a/?c\s*no|aic\s*no|account\s*no|ifsc|branch\s*code|mailing\s*address|statement\s*period)\b', re.IGNORECASE),
    re.compile(r'\b(account\s*type\s*:\s*savings\s*account|product\s*:\s*savings\s*account)\b', re.IGNORECASE),
]


def match_column_name(header_str: str) -> Optional[str]:
    """Match a header token/cell string to standard column name with robust punctuation tolerance."""
    if not header_str:
        return None
    raw = header_str.strip().lower()
    clean = re.sub(r'[^a-zA-Z0-9/().\s-]', '', raw)
    clean = re.sub(r'\s+', ' ', clean).strip()

    # Direct match first
    for col_key, patterns in SYNONYMS.items():
        for pat in patterns:
            if clean == pat:
                return col_key

    # Normalized match (strip dots and trailing punctuation)
    no_punct = clean.replace('.', '').replace(',', '').strip()
    no_punct = re.sub(r'\s+', ' ', no_punct)
    for col_key, patterns in SYNONYMS.items():
        for pat in patterns:
            p_clean = pat.replace('.', '').replace(',', '').strip()
            if no_punct == p_clean:
                return col_key

    return None


def is_skip_row(row_text: str) -> bool:
    """Check if row is a brought forward, total, or footer line."""
    if not row_text:
        return True
    # Never skip genuine interest credit or payment narrations that happen to contain keywords
    if re.search(r'\b(int\.?pd|interest\s*credit|upi|neft|rtgs|imps)\b', row_text, re.IGNORECASE):
        return False
    for p in SKIP_ROW_PATTERNS:
        if p.search(row_text):
            return True
    return False


def cluster_words_into_rows(words: List[Dict[str, Any]], y_tolerance: float = 4.0) -> List[List[Dict[str, Any]]]:
    """Group words with close y-coordinates into rows, sorted top-to-bottom and left-to-right."""
    if not words:
        return []

    sorted_words = sorted(words, key=lambda w: (w["top"], w["x0"]))
    rows: List[List[Dict[str, Any]]] = []

    for w in sorted_words:
        assigned = False
        for row in rows:
            avg_top = sum(item["top"] for item in row) / len(row)
            if abs(w["top"] - avg_top) <= y_tolerance:
                row.append(w)
                assigned = True
                break
        if not assigned:
            rows.append([w])

    for row in rows:
        row.sort(key=lambda w: w["x0"])

    rows.sort(key=lambda r: min(w["top"] for w in r))
    return rows


def detect_header_row(rows: List[List[Dict[str, Any]]]) -> Tuple[Optional[int], Dict[str, Tuple[float, float]]]:
    """
    Search rows for a transaction table header.
    Returns:
    (header_row_index, col_boundaries)
    where col_boundaries is dict mapping col_key -> (x_min, x_max).
    """
    best_row_idx = None
    best_cols: Dict[str, Tuple[float, float]] = {}
    max_matches = 0

    for idx, row in enumerate(rows):
        row_text = " ".join(w["text"] for w in row).lower()
        if not ("date" in row_text or "balance" in row_text or "amount" in row_text or "narration" in row_text or "debit" in row_text):
            continue

        cols_found: Dict[str, Dict[str, Any]] = {}
        i = 0
        while i < len(row):
            matched = False
            for span in [4, 3, 2, 1]:
                if i + span <= len(row):
                    # Check that words in multi-word span are contiguous (not separated by column gaps)
                    is_contig = True
                    for k in range(i, i + span - 1):
                        if (row[k + 1]["x0"] - row[k]["x1"]) > 25.0:
                            is_contig = False
                            break
                    if not is_contig:
                        continue
                    chunk_text = " ".join(row[j]["text"] for j in range(i, i + span))
                    col_key = match_column_name(chunk_text)
                    if col_key and col_key not in cols_found:
                        x0 = row[i]["x0"]
                        x1 = row[i + span - 1]["x1"]
                        cols_found[col_key] = {"x0": x0, "x1": x1, "mid": (x0 + x1) / 2.0}
                        i += span
                        matched = True
                        break
            if not matched:
                i += 1

        has_date = "date" in cols_found
        has_desc = "description" in cols_found or "amount" in cols_found
        has_money = "balance" in cols_found or "debit" in cols_found or "credit" in cols_found or "amount" in cols_found

        if has_date and (has_desc or has_money) and len(cols_found) > max_matches:
            # Check if description column is missing between date and money columns
            if "description" not in cols_found and "date" in cols_found:
                right_cols = [c for c, d in cols_found.items() if d["x0"] > cols_found["date"]["x1"]]
                if right_cols:
                    first_right = min(right_cols, key=lambda c: cols_found[c]["x0"])
                    gap = cols_found[first_right]["x0"] - cols_found["date"]["x1"]
                    if gap > 45.0:
                        desc_x0 = cols_found["date"]["x1"] + 2.0
                        desc_x1 = cols_found[first_right]["x0"] - 2.0
                        cols_found["description"] = {
                            "x0": desc_x0,
                            "x1": desc_x1,
                            "mid": (desc_x0 + desc_x1) / 2.0
                        }

            # Check if money column is missing between description and balance
            if "balance" in cols_found and not any(k in cols_found for k in ["amount", "debit", "credit"]):
                left_col = "description" if "description" in cols_found else ("date" if "date" in cols_found else None)
                if left_col:
                    gap = cols_found["balance"]["x0"] - cols_found[left_col]["x1"]
                    if gap > 55.0:
                        amt_x0 = cols_found[left_col]["x1"] + 2.0
                        amt_x1 = cols_found["balance"]["x0"] - 2.0
                        cols_found["amount"] = {
                            "x0": amt_x0,
                            "x1": amt_x1,
                            "mid": (amt_x0 + amt_x1) / 2.0
                        }

            max_matches = len(cols_found)
            best_row_idx = idx

            sorted_cols = sorted(cols_found.items(), key=lambda c: c[1]["mid"])
            boundaries: Dict[str, Tuple[float, float]] = {}

            for c_idx, (col_name, data) in enumerate(sorted_cols):
                if c_idx == 0:
                    left_bound = 0.0
                else:
                    prev_col, prev_data = sorted_cols[c_idx - 1]
                    if prev_col == "description" and col_name in ["amount", "debit", "credit"]:
                        left_bound = max((prev_data["x1"] + data["x0"]) / 2.0, data["x0"] - 35.0)
                    else:
                        left_bound = (prev_data["x1"] + data["x0"]) / 2.0

                if c_idx == len(sorted_cols) - 1:
                    right_bound = 10000.0
                else:
                    next_col, next_data = sorted_cols[c_idx + 1]
                    if col_name == "description" and next_col in ["amount", "debit", "credit"]:
                        right_bound = max((data["x1"] + next_data["x0"]) / 2.0, next_data["x0"] - 35.0)
                    else:
                        right_bound = (data["x1"] + next_data["x0"]) / 2.0

                boundaries[col_name] = (left_bound, right_bound)

            best_cols = boundaries

    return best_row_idx, best_cols


def infer_boundaries_from_data(
    rows: List[List[Dict[str, Any]]]
) -> Dict[str, Tuple[float, float]]:
    """
    When no header row is found (or header is incomplete), attempt to infer column
    boundaries by scanning data rows for date and numeric patterns.

    Strategy:
    - Date column: leftmost region containing valid date patterns (bounded to ~120)
    - Strict currency patterns: must have decimal or Dr/Cr or brackets (excludes ref/account numbers)
    - Balance column: rightmost cluster (typically x > 470)
    - Amount/transaction column: cluster before balance (typically 280 < x < 480)
    - Description: everything between date and amount/balance
    """
    date_xs: List[float] = []
    amt_xs: List[float] = []
    bal_xs: List[float] = []

    _CURR_RE = re.compile(
        r'[\d,]+\.\d{2}(Dr|Cr|DR|CR)?|[\d,]+(Dr|Cr|DR|CR)|\([\d,]+(\.\d{2})?\)',
        re.I
    )

    for row in rows:
        row_str = " ".join(w["text"] for w in row)
        if is_skip_row(row_str):
            continue

        # Check adjacent-word date spans (e.g. "Jun 01, 2026" or "01 Jan 2026")
        for span_len in [3, 2, 1]:
            for start in range(min(4, max(0, len(row) - span_len + 1))):
                words_span = row[start: start + span_len]
                combined = " ".join(w["text"] for w in words_span).strip(".,;:\"'`~")
                if parse_date(combined):
                    date_xs.append(words_span[-1]["x1"])
                    break

        for w in row:
            txt = w["text"].strip("\"'`\u2018\u2019\u201c\u201d*~")
            if _CURR_RE.search(txt):
                x0 = w["x0"]
                if x0 > 470:
                    bal_xs.append(x0)
                elif x0 > 280:
                    amt_xs.append(x0)

    # Determine date right edge
    date_right = min(max(date_xs) + 15.0, 120.0) if date_xs else 85.0

    # Determine amount & balance columns
    boundaries: Dict[str, Tuple[float, float]] = {}
    boundaries["date"] = (0.0, date_right)

    if bal_xs and amt_xs:
        amt_left = max(date_right + 10.0, min(amt_xs) - 15.0)
        bal_left = max(amt_left + 40.0, min(bal_xs) - 15.0)
        boundaries["description"] = (date_right, amt_left)
        boundaries["amount"] = (amt_left, bal_left)
        boundaries["balance"] = (bal_left, 10000.0)
    elif bal_xs:
        bal_left = max(date_right + 50.0, min(bal_xs) - 15.0)
        boundaries["description"] = (date_right, bal_left)
        boundaries["balance"] = (bal_left, 10000.0)
    elif amt_xs:
        amt_left = max(date_right + 50.0, min(amt_xs) - 15.0)
        boundaries["description"] = (date_right, amt_left)
        boundaries["amount"] = (amt_left, 10000.0)
    else:
        # Fallback default A4 boundaries
        boundaries["description"] = (date_right, 400.0)
        boundaries["amount"] = (400.0, 480.0)
        boundaries["balance"] = (480.0, 10000.0)

    return boundaries


def parse_geometry_transactions(
    rows: List[List[Dict[str, Any]]],
    col_boundaries: Dict[str, Tuple[float, float]],
    source_file: str = "",
    page_num: int = 1
) -> List[Transaction]:
    """Parse clustered rows into transactions using column boundaries with multi-line support."""
    txns: List[Transaction] = []
    current_txn: Optional[Transaction] = None
    pending_prefix: List[str] = []
    last_balance: Optional[float] = None

    for row in rows:
        row_str = " ".join(w["text"] for w in row).strip()
        if not row_str or is_skip_row(row_str):
            continue

        # Bin words into columns
        col_cells: Dict[str, List[str]] = {c: [] for c in col_boundaries}
        row_confs = []
        x0_min = min(w["x0"] for w in row)
        x1_max = max(w["x1"] for w in row)
        top_min = min(w["top"] for w in row)
        bot_max = max(w["bottom"] for w in row)

        for w in row:
            row_confs.append(w.get("confidence", 1.0))
            mid_x = (w["x0"] + w["x1"]) / 2.0
            for c_name, (c_left, c_right) in col_boundaries.items():
                if c_left <= mid_x < c_right:
                    col_cells[c_name].append(w["text"])
                    break

        # Move any purely alphabetical spillover words from numeric columns back to description
        for num_col in ["amount", "debit", "credit"]:
            if num_col in col_cells and col_cells[num_col]:
                pure_text_words = []
                remaining_words = []
                for w_txt in col_cells[num_col]:
                    w_upper = w_txt.upper().strip(".,()[]-+/")
                    if w_upper not in ["DR", "CR", "INR", "RS", "USD", "EUR", ""] and not any(ch.isdigit() for ch in w_txt):
                        pure_text_words.append(w_txt)
                    else:
                        remaining_words.append(w_txt)
                if pure_text_words:
                    col_cells[num_col] = remaining_words
                    if "description" in col_cells:
                        col_cells["description"].extend(pure_text_words)

        cell_values = {c: " ".join(col_cells[c]).strip() for c in col_boundaries}
        date_raw = cell_values.get("date", "")
        parsed_d = parse_date(date_raw)

        if not parsed_d:
            cand_tokens = date_raw.split() if date_raw else [w["text"] for w in row[:5]]
            for span in [3, 2, 1]:
                for idx in range(min(4, len(cand_tokens) - span + 1)):
                    sub = " ".join(cand_tokens[idx:idx + span]).strip(".,;:\"'`~")
                    d_try = parse_date(sub)
                    if d_try:
                        parsed_d = d_try
                        if date_raw:
                            rem = " ".join(cand_tokens[:idx] + cand_tokens[idx + span:]).strip()
                            if rem:
                                cell_values["description"] = (rem + " " + cell_values.get("description", "")).strip()
                        break
                if parsed_d:
                    break

        if parsed_d:
            val_date = parse_date(cell_values.get("value_date", ""))
            desc = cell_values.get("description", "")
            if pending_prefix:
                prefix_str = " ".join(pending_prefix).strip()
                desc = (prefix_str + " " + desc).strip()
                pending_prefix = []

            ref_no = cell_values.get("ref_no", "") or None

            balance = None
            if "balance" in col_boundaries:
                bal_raw = cell_values.get("balance", "")
                bal_amt, _ = parse_amount(bal_raw)
                balance = bal_amt

            debit_amt: Optional[float] = None
            credit_amt: Optional[float] = None

            if "debit" in col_boundaries and "credit" in col_boundaries:
                d_raw = cell_values.get("debit", "")
                c_raw = cell_values.get("credit", "")
                d_val, _ = parse_amount(d_raw)
                c_val, _ = parse_amount(c_raw)
                debit_amt, credit_amt = resolve_split_debit_credit(
                    d_raw=d_raw,
                    c_raw=c_raw,
                    d_val=d_val,
                    c_val=c_val,
                    last_balance=last_balance,
                    current_balance=balance
                )
            elif "amount" in col_boundaries and "indicator" in col_boundaries:
                a_raw = cell_values.get("amount", "")
                ind_raw = cell_values.get("indicator", "").upper()
                a_val, ind_dir = parse_amount(a_raw)
                if not ind_dir:
                    ind_dir = "DR" if "DR" in ind_raw else ("CR" if "CR" in ind_raw else None)
                if ind_dir == "DR":
                    debit_amt = a_val
                elif ind_dir == "CR":
                    credit_amt = a_val
                else:
                    if last_balance is not None and balance is not None and balance > last_balance + 0.01:
                        credit_amt = a_val
                    else:
                        debit_amt = a_val
            elif "amount" in col_boundaries:
                a_raw = cell_values.get("amount", "")
                a_val, a_dir = parse_amount(a_raw)
                is_neg = a_raw.strip().startswith("-") or (a_raw.strip().startswith("(") and a_raw.strip().endswith(")"))
                if a_dir == "DR" or is_neg:
                    debit_amt = a_val
                elif a_dir == "CR" or a_raw.startswith("+"):
                    credit_amt = a_val
                else:
                    desc_upper = desc.upper()
                    if any(w in desc_upper for w in ["CASH DEPOSIT", "DEPOSIT", "SALARY", "INTEREST CREDIT", "REFUND", "REVERSAL", "TRANSFER IN"]):
                        credit_amt = a_val
                    elif last_balance is not None and balance is not None and balance > last_balance + 0.01:
                        credit_amt = a_val
                    elif last_balance is not None and balance is not None and balance < last_balance - 0.01:
                        debit_amt = a_val
                    else:
                        debit_amt = a_val

            # Fallback: if OCR dropped/smeared the amount, recover it from running balance delta
            if debit_amt is None and credit_amt is None:
                if last_balance is not None and balance is not None:
                    delta = round(balance - last_balance, 2)
                    if delta > 0.01:
                        credit_amt = delta
                    elif delta < -0.01:
                        debit_amt = abs(delta)

            if balance is not None and balance > 0:
                last_balance = balance

            avg_ocr_conf = (sum(row_confs) / len(row_confs)) if row_confs else 1.0

            current_txn = Transaction(
                date=parsed_d,
                value_date=val_date or parsed_d,
                description=desc,
                ref_no=ref_no,
                debit=debit_amt,
                credit=credit_amt,
                balance=balance,
                source_file=source_file,
                page=page_num,
                bbox=[x0_min, top_min, x1_max, bot_max],
                ocr_confidence=avg_ocr_conf
            )
            txns.append(current_txn)
        else:
            extra_text = cell_values.get("description", "") or row_str
            if extra_text and not is_skip_row(extra_text):
                if current_txn is not None:
                    current_txn.description = (current_txn.description + " " + extra_text).strip()
                    if current_txn.bbox:
                        current_txn.bbox[2] = max(current_txn.bbox[2], x1_max)
                        current_txn.bbox[3] = max(current_txn.bbox[3], bot_max)
                else:
                    pending_prefix.append(extra_text)

    return txns


def parse_table_matrix(
    matrix: List[List[Optional[str]]],
    source_file: str = "",
    page_num: int = 1
) -> List[Transaction]:
    """Parse pdfplumber extracted table matrix into Transactions."""
    if not matrix or len(matrix) < 2:
        return []

    header_idx = None
    col_map: Dict[str, int] = {}

    for r_idx, row in enumerate(matrix):
        clean_row = [str(c or "").strip() for c in row]
        row_cols = {}
        for c_idx, cell in enumerate(clean_row):
            matched = match_column_name(cell)
            if matched and matched not in row_cols:
                row_cols[matched] = c_idx
        if "date" in row_cols and ("balance" in row_cols or "amount" in row_cols or "debit" in row_cols):
            header_idx = r_idx
            col_map = row_cols
            break

    if header_idx is None:
        return []

    txns: List[Transaction] = []
    current_txn: Optional[Transaction] = None
    last_balance: Optional[float] = None

    for row in matrix[header_idx + 1:]:
        clean_cells = [str(c or "").strip() for c in row]
        row_str = " ".join(clean_cells)
        if not row_str or is_skip_row(row_str):
            continue

        date_col = col_map.get("date")
        date_raw = clean_cells[date_col] if date_col is not None and date_col < len(clean_cells) else ""
        parsed_d = parse_date(date_raw)

        if parsed_d:
            val_date_col = col_map.get("value_date")
            val_d_raw = clean_cells[val_date_col] if val_date_col is not None and val_date_col < len(clean_cells) else ""
            val_date = parse_date(val_d_raw)

            desc_col = col_map.get("description")
            desc = clean_cells[desc_col] if desc_col is not None and desc_col < len(clean_cells) else ""

            ref_col = col_map.get("ref_no")
            ref_no = clean_cells[ref_col] if ref_col is not None and ref_col < len(clean_cells) else None

            balance = None
            if "balance" in col_map:
                bal_col = col_map.get("balance")
                bal_raw = clean_cells[bal_col] if bal_col is not None and bal_col < len(clean_cells) else ""
                bal_amt, _ = parse_amount(bal_raw)
                balance = bal_amt if bal_amt is not None else 0.0

            debit_amt: Optional[float] = None
            credit_amt: Optional[float] = None

            if "debit" in col_map and "credit" in col_map:
                d_raw = clean_cells[col_map["debit"]] if col_map["debit"] < len(clean_cells) else ""
                c_raw = clean_cells[col_map["credit"]] if col_map["credit"] < len(clean_cells) else ""
                d_val, _ = parse_amount(d_raw)
                c_val, _ = parse_amount(c_raw)
                debit_amt, credit_amt = resolve_split_debit_credit(
                    d_raw=d_raw,
                    c_raw=c_raw,
                    d_val=d_val,
                    c_val=c_val,
                    last_balance=last_balance,
                    current_balance=balance
                )
            elif "amount" in col_map and "indicator" in col_map:
                a_raw = clean_cells[col_map["amount"]] if col_map["amount"] < len(clean_cells) else ""
                ind_raw = clean_cells[col_map["indicator"]] if col_map["indicator"] < len(clean_cells) else ""
                a_val, ind_dir = parse_amount(a_raw)
                if not ind_dir:
                    ind_dir = "DR" if "DR" in ind_raw.upper() else ("CR" if "CR" in ind_raw.upper() else None)
                if ind_dir == "DR":
                    debit_amt = a_val
                elif ind_dir == "CR":
                    credit_amt = a_val
                else:
                    if last_balance is not None and balance is not None and balance > last_balance + 0.01:
                        credit_amt = a_val
                    else:
                        debit_amt = a_val
            elif "amount" in col_map:
                a_raw = clean_cells[col_map["amount"]] if col_map["amount"] < len(clean_cells) else ""
                a_val, a_dir = parse_amount(a_raw)
                is_neg = a_raw.strip().startswith("-") or (a_raw.strip().startswith("(") and a_raw.strip().endswith(")"))
                if a_dir == "DR" or is_neg:
                    debit_amt = a_val
                elif a_dir == "CR" or a_raw.startswith("+"):
                    credit_amt = a_val
                else:
                    desc_upper = desc.upper()
                    if any(w in desc_upper for w in ["CASH DEPOSIT", "DEPOSIT", "SALARY", "INTEREST CREDIT", "REFUND", "REVERSAL", "TRANSFER IN"]):
                        credit_amt = a_val
                    elif last_balance is not None and balance is not None and balance > last_balance + 0.01:
                        credit_amt = a_val
                    elif last_balance is not None and balance is not None and balance < last_balance - 0.01:
                        debit_amt = a_val
                    else:
                        debit_amt = a_val

            # Fallback: if OCR dropped/smeared the amount, recover it from running balance delta
            if debit_amt is None and credit_amt is None:
                if last_balance is not None and balance is not None:
                    delta = round(balance - last_balance, 2)
                    if delta > 0.01:
                        credit_amt = delta
                    elif delta < -0.01:
                        debit_amt = abs(delta)

            if balance is not None and balance > 0:
                last_balance = balance

            current_txn = Transaction(
                date=parsed_d,
                value_date=val_date or parsed_d,
                description=desc.replace('\n', ' '),
                ref_no=ref_no,
                debit=debit_amt,
                credit=credit_amt,
                balance=balance,
                source_file=source_file,
                page=page_num,
                ocr_confidence=1.0
            )
            txns.append(current_txn)
        else:
            if current_txn is not None:
                desc_col = col_map.get("description")
                extra = clean_cells[desc_col] if desc_col is not None and desc_col < len(clean_cells) else row_str
                if extra and not is_skip_row(extra):
                    current_txn.description = (current_txn.description + " " + extra.replace('\n', ' ')).strip()

    return txns


def extract_transactions_from_page(
    pdf_path: str,
    page_number: int,
    is_scanned: bool = False,
    saved_boundaries: Optional[Dict[str, Tuple[float, float]]] = None,
    dpi: int = 300,
    password: str = ""
) -> Tuple[List[Transaction], Dict[str, Tuple[float, float]]]:
    """
    Unified page transaction extractor:
    - First attempts pdfplumber structured tables if text PDF.
    - If no table found, uses geometry / word clustering.
    - If scanned, renders high-res image and uses Tesseract OCR + geometry parser.
    """
    # 1. Try table extraction on text PDFs
    if not is_scanned:
        try:
            tables = extract_tables_from_page(pdf_path, page_number, password=password)
            for matrix in tables:
                txns = parse_table_matrix(matrix, source_file=os.path.basename(pdf_path), page_num=page_number)
                if txns:
                    return txns, saved_boundaries or {}
        except Exception:
            pass

    # 2. Geometry / OCR path
    if is_scanned:
        words = []
        from core.ocr_extractor import is_tesseract_available
        if is_tesseract_available():
            try:
                words, _ = extract_words_from_scanned_page(pdf_path, page_number, dpi=dpi, password=password)
            except Exception:
                words = []
        if not words:
            # Fall back to text extraction (works for hybrid/embedded text layers without Tesseract)
            words = extract_words_from_page(pdf_path, page_number, password=password)
        y_tol = 5.0
        # Strip OCR noise characters that act as column separators (e.g. pipe from table borders)
        _NOISE_CHARS = {'|', '│', '┃', '—', '―', ''}
        words = [w for w in words if w.get('text', '').strip() not in _NOISE_CHARS]
    else:
        words = extract_words_from_page(pdf_path, page_number, password=password)
        y_tol = 4.0

    rows = cluster_words_into_rows(words, y_tolerance=y_tol)
    h_idx, boundaries = detect_header_row(rows)

    # Determine whether the detected boundaries are "complete" (have key money columns)
    _KEY_MONEY_COLS = {'debit', 'credit', 'amount', 'withdrawal', 'deposit'}
    detected_has_money = bool(boundaries and (_KEY_MONEY_COLS & set(boundaries.keys())))
    saved_has_money = bool(saved_boundaries and (_KEY_MONEY_COLS & set(saved_boundaries.keys())))

    # If partial header was detected without money columns, complement with inferred boundaries from data
    if boundaries and not detected_has_money:
        inferred = infer_boundaries_from_data(rows)
        if inferred:
            for k, v in inferred.items():
                if k not in boundaries:
                    boundaries[k] = v
            if "description" in boundaries:
                money_lefts = [boundaries[m][0] for m in ["amount", "debit", "credit", "balance"] if m in boundaries]
                if money_lefts:
                    boundaries["description"] = (boundaries["description"][0], min(money_lefts))
            detected_has_money = bool(boundaries and (_KEY_MONEY_COLS & set(boundaries.keys())))

    # Calculate row start index, skipping multi-line headers if present
    start_idx = 0
    if h_idx is not None:
        start_idx = h_idx + 1
        if start_idx < len(rows):
            next_row_text = " ".join(w["text"] for w in rows[start_idx]).strip().lower()
            if any(kw in next_row_text for kw in ["remarks", "(inr)", "inr", "particulars", "details", "cheque", "value dt"]):
                start_idx += 1

    if h_idx is not None and boundaries and detected_has_money:
        # Full header found on this page — use freshly detected boundaries
        txns = parse_geometry_transactions(
            rows[start_idx:],
            boundaries,
            source_file=os.path.basename(pdf_path),
            page_num=page_number
        )
        return txns, boundaries
    elif saved_boundaries and saved_has_money:
        # Continuation page: reuse saved column boundaries from prior page.
        txns = parse_geometry_transactions(
            rows[start_idx:],
            saved_boundaries,
            source_file=os.path.basename(pdf_path),
            page_num=page_number
        )
        return txns, saved_boundaries
    elif h_idx is not None and boundaries:
        # Partial header detected and no saved boundaries — use what we have
        txns = parse_geometry_transactions(
            rows[start_idx:],
            boundaries,
            source_file=os.path.basename(pdf_path),
            page_num=page_number
        )
        if txns:
            return txns, boundaries

    # 3. Fallback: if header detection yielded nothing or had no transactions, infer boundaries from data
    inferred = infer_boundaries_from_data(rows)
    if inferred and "date" in inferred:
        txns = parse_geometry_transactions(
            rows[start_idx:],
            inferred,
            source_file=os.path.basename(pdf_path),
            page_num=page_number
        )
        if txns:
            return txns, inferred

    return [], {}
