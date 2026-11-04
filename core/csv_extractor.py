"""CSV Statement parser for bank and ground truth CSV files."""

import csv
import os
import re
from typing import List, Tuple, Dict, Any, Optional
from core.models import Transaction, AccountDetails
from core.amount_date_parser import parse_date, parse_amount, resolve_split_debit_credit
from core.layout_parser import match_column_name


def parse_csv_transactions(csv_path: str, filename: str = "") -> Tuple[List[Transaction], AccountDetails]:
    """
    Parse a CSV bank statement or ground truth CSV into Transactions and AccountDetails.
    Supports comma, semicolon, and tab-delimited files.
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    # Sniff encoding (utf-8-sig handles BOM, utf-8, latin-1 fallback)
    content = ""
    for enc in ["utf-8-sig", "utf-8", "latin-1"]:
        try:
            with open(csv_path, "r", encoding=enc) as f:
                content = f.read()
            break
        except Exception:
            continue

    if not content:
        return [], AccountDetails(bank_name="CSV Statement", source_file=filename)

    lines = content.splitlines()
    if not lines:
        return [], AccountDetails(bank_name="CSV Statement", source_file=filename)

    # Sniff delimiter
    first_line = lines[0]
    delimiter = ","
    if "\t" in first_line:
        delimiter = "\t"
    elif ";" in first_line and first_line.count(";") > first_line.count(","):
        delimiter = ";"

    reader = csv.reader(lines, delimiter=delimiter)
    raw_rows = list(reader)

    if not raw_rows:
        return [], AccountDetails(bank_name="CSV Statement", source_file=filename)

    # Locate header row
    header_idx = None
    col_map: Dict[str, int] = {}

    for r_idx, row in enumerate(raw_rows[:15]):
        cur_cols = {}
        for c_idx, cell in enumerate(row):
            token = str(cell or "").strip()
            # Match directly or via synonyms
            matched = match_column_name(token)
            if matched and matched not in cur_cols:
                cur_cols[matched] = c_idx
            elif token.lower() in ["ref", "reference", "ref_no"]:
                cur_cols["ref_no"] = c_idx
            elif token.lower() in ["category"]:
                cur_cols["category"] = c_idx
            elif token.lower() in ["direction", "dir", "type", "drcr", "dr/cr", "cr/dr"]:
                cur_cols["direction"] = c_idx

        # If date and at least one money/desc column matched, this is our header
        if "date" in cur_cols and ("description" in cur_cols or "amount" in cur_cols or "debit" in cur_cols or "balance" in cur_cols):
            header_idx = r_idx
            col_map = cur_cols
            break
        # Also match classification data files without dates
        elif "description" in cur_cols and ("amount" in cur_cols or "debit" in cur_cols or "credit" in cur_cols):
            header_idx = r_idx
            col_map = cur_cols
            break

    # If no header matched via match_column_name, fall back to simple lowercase column matching
    if header_idx is None:
        header_row = [c.strip().lower() for c in raw_rows[0]]
        col_map = {}
        for idx, col in enumerate(header_row):
            if "date" in col:
                col_map["date"] = idx
            elif any(k in col for k in ["desc", "particular", "narration", "detail"]):
                col_map["description"] = idx
            elif "debit" in col or "withdrawal" in col:
                col_map["debit"] = idx
            elif "credit" in col or "deposit" in col:
                col_map["credit"] = idx
            elif "bal" in col:
                col_map["balance"] = idx
            elif "amt" in col or "amount" in col:
                col_map["amount"] = idx
            elif "dir" in col or "type" in col or "indicator" in col:
                col_map["direction"] = idx
            elif "ref" in col or "chq" in col:
                col_map["ref_no"] = idx
            elif "cat" in col:
                col_map["category"] = idx
        if "date" in col_map or "description" in col_map:
            header_idx = 0

    if header_idx is None or ("date" not in col_map and "description" not in col_map):
        return [], AccountDetails(bank_name="CSV Statement", source_file=filename)

    transactions: List[Transaction] = []
    last_balance: Optional[float] = None
    opening_bal: Optional[float] = None

    for r_idx in range(header_idx + 1, len(raw_rows)):
        row = raw_rows[r_idx]
        if not row or not any(cell.strip() for cell in row):
            continue

        def get_val(col_key: str) -> str:
            if col_key in col_map and col_map[col_key] < len(row):
                return str(row[col_map[col_key]]).strip()
            return ""

        if "date" in col_map:
            date_raw = get_val("date")
            parsed_d = parse_date(date_raw)
            if not parsed_d:
                continue
        else:
            # Generate sequential dates for classification datasets
            from datetime import date as dt_date, timedelta
            base_date = dt_date(2026, 1, 1)
            row_offset = (r_idx - header_idx - 1) % 365
            parsed_d = (base_date + timedelta(days=row_offset)).strftime("%Y-%m-%d")

        desc = get_val("description")
        ref_no = get_val("ref_no") or None
        cat = get_val("category") or None

        balance_val = None
        bal_raw = get_val("balance")
        if bal_raw:
            b_amt, _ = parse_amount(bal_raw)
            balance_val = b_amt

        debit_val = None
        credit_val = None

        dir_raw = get_val("direction").upper() if "direction" in col_map else ""

        if "debit" in col_map and "credit" in col_map:
            d_raw = get_val("debit")
            c_raw = get_val("credit")
            d_amt, _ = parse_amount(d_raw)
            c_amt, _ = parse_amount(c_raw)
            debit_val, credit_val = resolve_split_debit_credit(
                d_raw=d_raw,
                c_raw=c_raw,
                d_val=d_amt,
                c_val=c_amt,
                last_balance=last_balance,
                current_balance=balance_val
            )
        elif "amount" in col_map:
            a_raw = get_val("amount")
            a_amt, ind_dir = parse_amount(a_raw)
            if not ind_dir and dir_raw:
                ind_dir = "DR" if "DR" in dir_raw else ("CR" if "CR" in dir_raw else None)
            is_neg = a_raw.startswith("-") or (a_raw.startswith("(") and a_raw.endswith(")"))
            if ind_dir == "DR" or is_neg:
                debit_val = a_amt
            elif ind_dir == "CR" or a_raw.startswith("+"):
                credit_val = a_amt
            else:
                if last_balance is not None and balance_val is not None and balance_val > last_balance + 0.01:
                    credit_val = a_amt
                else:
                    debit_val = a_amt

        if opening_bal is None and balance_val is not None:
            opening_bal = balance_val + (debit_val or 0.0) - (credit_val or 0.0)

        if balance_val is not None:
            last_balance = balance_val

        txn = Transaction(
            date=parsed_d,
            description=desc,
            ref_no=ref_no,
            debit=debit_val,
            credit=credit_val,
            balance=balance_val,
            category=cat or "Uncategorized",
            category_confidence=1.0 if cat else 0.0,
            classification_source="manual" if cat else "rule",
            source_file=filename,
            page=1,
            ocr_confidence=1.0
        )
        transactions.append(txn)

    # Clean bank name from filename
    bank_name = "Imported Statement"
    clean_fn = os.path.basename(filename)
    if "hdfc" in clean_fn.lower(): bank_name = "HDFC Bank"
    elif "icici" in clean_fn.lower(): bank_name = "ICICI Bank"
    elif "sbi" in clean_fn.lower(): bank_name = "State Bank of India"
    elif "kotak" in clean_fn.lower(): bank_name = "Kotak Mahindra Bank"
    elif "axis" in clean_fn.lower(): bank_name = "Axis Bank"

    account = AccountDetails(
        bank_name=bank_name,
        account_number="CSV-IMPORT",
        opening_balance=round(opening_bal, 2) if opening_bal is not None else None,
        closing_balance=round(last_balance, 2) if last_balance is not None else None,
        source_file=filename,
        pdf_type="csv",
        total_pages=1,
        page_types={1: "text"}
    )

    return transactions, account

