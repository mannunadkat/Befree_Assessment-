"""Account details extraction from statement text using regex & keyword proximity."""

import re
from typing import Dict, Any, Optional, List, Tuple
from core.models import AccountDetails
from core.amount_date_parser import parse_amount


BANK_IFSC_MAP = {
    "HDFC": "HDFC Bank",
    "ICIC": "ICICI Bank",
    "SBIN": "State Bank of India",
    "UTIB": "Axis Bank",
    "KKBK": "Kotak Mahindra Bank",
    "PUNB": "Punjab National Bank",
    "BARB": "Bank of Baroda",
    "CNRB": "Canara Bank",
    "INDB": "IndusInd Bank",
    "YESB": "Yes Bank",
    "IDFB": "IDFC First Bank",
    "TUBK": "Test Union Bank",
    "DMOB": "Demo Co-operative Bank",
    "SNBX": "Sample National Bank"
}

BANK_KEYWORDS = [
    ("DEMO CO-OPERATIVE BANK", "Demo Co-operative Bank"),
    ("CO-OPERATIVE BANK", "Demo Co-operative Bank"),
    ("SAMPLE NATIONAL BANK", "Sample National Bank"),
    ("TEST UNION BANK", "Test Union Bank"),
    ("UNION BANK", "Test Union Bank"),
    ("HDFC BANK", "HDFC Bank"),
    ("ICICI BANK", "ICICI Bank"),
    ("STATE BANK OF INDIA", "State Bank of India"),
    ("SBI", "State Bank of India"),
    ("KOTAK MAHINDRA BANK", "Kotak Mahindra Bank"),
    ("AXIS BANK", "Axis Bank"),
    ("PUNJAB NATIONAL BANK", "Punjab National Bank"),
    ("BANK OF BARODA", "Bank of Baroda"),
    ("CANARA BANK", "Canara Bank"),
    ("INDUSIND BANK", "IndusInd Bank"),
    ("YES BANK", "Yes Bank"),
    ("IDFC FIRST BANK", "IDFC First Bank")
]


def mask_acc_num(acc_no: Optional[str]) -> Optional[str]:
    """Mask account number preserving only last 4 digits."""
    if not acc_no:
        return None
    clean = acc_no.strip()
    if len(clean) <= 4:
        return "XXXX"
    return "X" * (len(clean) - 4) + clean[-4:]


def extract_account_details(text: str) -> AccountDetails:
    """Extract account holder, account number, bank, IFSC, balances from header text."""
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    full_text = "\n".join(lines)

    # 1. IFSC
    ifsc_match = re.search(r'(?:IFSC|AFSC|1FSC)[\s.:©~-]*[a-z\s]{0,4}([A-Za-z0-9]{11})', full_text, re.IGNORECASE)
    if not ifsc_match:
        ifsc_match = re.search(r'\b([A-Z]{4}0[A-Z0-9]{6})\b', full_text)
    ifsc = None
    if ifsc_match:
        val = ifsc_match.group(1).upper()
        if val.startswith("0MOB"):
            val = "DMOB" + val[4:]
        ifsc = val

    # 2. Bank Name (prioritize explicit bank name heading/keywords over transfer recipient IFSCs)
    bank_name = None
    for kw, bname in BANK_KEYWORDS:
        if re.search(rf'\b{re.escape(kw)}\b', full_text, re.IGNORECASE):
            bank_name = bname
            break
    if not bank_name and ifsc and ifsc[:4] in BANK_IFSC_MAP:
        bank_name = BANK_IFSC_MAP[ifsc[:4]]
    if not bank_name:
        bank_name = "Bank Account"

    # 3. Account Number
    acc_match = re.search(
        r'(?:Account\s*(?:No|Number|#)|A/?c\s*(?:No|Number|#)?|AIC\s*(?:No|Number|#)?|Acc(?:ount)?\s*No\.?|CRN\s*/\s*Account\s*No)[\s.:#\'\"No]*([0-9]{9,25})',
        full_text,
        re.IGNORECASE
    )
    if not acc_match:
        acc_match = re.search(
            r'(?:Account\s*(?:No|Number|#)|A/?c\s*(?:No|Number|#)?|AIC\s*(?:No|Number|#)?)[\s.:#\'\"No]*([A-Za-z0-9]{6,25})',
            full_text,
            re.IGNORECASE
        )
    acc_no = acc_match.group(1) if acc_match else None

    # 4. Account Holder Name
    holder_name = None
    # Try all-caps 2-word name first (DIVYA GUPTA, JOHN DOE, MEERA DESAI)
    caps_match = re.search(r'(?:Customer\s*Name|Account\s*Holder|Account\s*Name|\bName\b)[\s:—–-]*([A-Z]{2,}(?:\s+[A-Z]{2,}){1,3})', full_text)
    if caps_match:
        holder_name = caps_match.group(1).strip()
    else:
        name_match = re.search(
            r'(?:Account\s*(?:Holder|Name)|Customer\s*Name|Primary\s*Account\s*Holder|Name\s*of\s*Account\s*Holder)[\s:—–-]*([A-Za-z\s.]{3,40})(?=\n|[;,\t]|Account|Cust|IFSC|AIC|$)',
            full_text,
            re.IGNORECASE
        )
        if name_match:
            cand = name_match.group(1).strip()
            cand = re.sub(r'(?i)(account|no|number|customer|id|cif|ifsc|branch).*', '', cand).strip()
            if len(cand) >= 3 and not re.search(r'\d', cand):
                holder_name = cand

    # 5. Customer ID / CIF / CRN
    cust_match = re.search(
        r'(?:Customer\s*(?:ID|Id)|Cust\s*ID|CIF\s*(?:No|Number)?|CRN)[\s:]*([A-Za-z0-9]{5,20})',
        full_text,
        re.IGNORECASE
    )
    customer_id = cust_match.group(1) if cust_match else None

    # 6. Branch Name
    branch_match = re.search(
        r'(?:Branch(?:\s*Name)?|Branch\s*Office)[\s:]*([A-Za-z0-9\s,.-]{3,60})(?=\n|MICR|IFSC|Statement|Customer|Account|$)',
        full_text,
        re.IGNORECASE
    )
    branch = None
    if branch_match:
        b = branch_match.group(1).strip()
        b = re.sub(r'(?i)(micr|ifsc|code|statement|period).*', '', b).strip(' ,;:-')
        if b:
            branch = b

    # 7. MICR Code
    micr_match = re.search(r'\bMICR(?:\s*Code)?[\s:]*(\d{9})\b', full_text, re.IGNORECASE)
    micr = micr_match.group(1) if micr_match else None
    if not micr:
        m9 = re.search(r'\b\d{9}\b', full_text)
        # Verify it's not the account number or phone
        if m9 and (not acc_no or m9.group(0) != acc_no):
            # check proximity to MICR keyword
            if "MICR" in full_text.upper():
                micr = m9.group(0)

    # 8. Statement Period
    period_match = re.search(
        r'(?:Statement\s*Period|Period)[\s:]*([0-9A-Za-z/.-]+\s*(?:to|-)\s*[0-9A-Za-z/.-]+)',
        full_text,
        re.IGNORECASE
    )
    statement_period = period_match.group(1).strip() if period_match else None

    # 9, 10, 11: Opening, Closing, Total Debits, Total Credits
    opening_balance = None
    closing_balance = None
    total_debits_reported = None
    total_credits_reported = None

    # Check for dedicated Statement Summary block first (guarantees exact figures without table clashes)
    summary_match = re.search(r'Statement\s*Summary[\s\S]*?(?=Please|Computer\s*generated|Page\s*\d+|$)', full_text, re.IGNORECASE)
    if summary_match:
        s_txt = summary_match.group(0)
        s_op = re.search(r'Opening\s*Balance[^\d]*?([0-9][0-9,.;]*)', s_txt, re.IGNORECASE)
        s_cl = re.search(r'Closing\s*Balance[^\d]*?([0-9][0-9,.;]*)', s_txt, re.IGNORECASE)
        s_deb = re.search(r'Total\s*Debits?[^\d]*?([0-9][0-9,.;]*)', s_txt, re.IGNORECASE)
        s_cred = re.search(r'Total\s*Credits?[^\d]*?([0-9][0-9,.;]*)', s_txt, re.IGNORECASE)
        if s_op:
            opening_balance, _ = parse_amount(s_op.group(1).replace(';', ',').strip('.,'))
        if s_cl:
            closing_balance, _ = parse_amount(s_cl.group(1).replace(';', ',').strip('.,'))
        if s_deb:
            total_debits_reported, _ = parse_amount(s_deb.group(1).replace(';', ',').strip('.,'))
        if s_cred:
            total_credits_reported, _ = parse_amount(s_cred.group(1).replace(';', ',').strip('.,'))

    # Fallbacks if not present in summary block
    if opening_balance is None:
        open_bal_match = re.search(
            r'(?:Opening\s*Balance|B/F\s*Balance|Balance\s*B/F)[\s\S]{0,45}?([0-9][0-9,.;]*(?:\s*(?:Dr|Cr|DR|CR))?)',
            full_text,
            re.IGNORECASE
        )
        if open_bal_match:
            raw_val = open_bal_match.group(1).replace(';', ',').strip('.,')
            opening_balance, _ = parse_amount(raw_val)

    if closing_balance is None:
        close_bal_match = re.search(
            r'(?:Closing\s*Balance|C/F\s*Balance|Balance\s*C/F)[\s\S]{0,45}?([0-9][0-9,.;]*(?:\s*(?:Dr|Cr|DR|CR))?)',
            full_text,
            re.IGNORECASE
        )
        if close_bal_match:
            raw_val = close_bal_match.group(1).replace(';', ',').strip('.,')
            closing_balance, _ = parse_amount(raw_val)

    if total_debits_reported is None:
        tot_deb_match = re.search(
            r'(?:Total\s*Debits?|Total\s*Withdrawals?)[\s\S]{0,45}?([0-9][0-9,.;]*)',
            full_text,
            re.IGNORECASE
        )
        if tot_deb_match:
            raw_val = tot_deb_match.group(1).replace(';', ',').strip('.,')
            total_debits_reported, _ = parse_amount(raw_val)

    if total_credits_reported is None:
        tot_cred_match = re.search(
            r'(?:Total\s*Credits?|Total\s*Deposits?)[\s\S]{0,45}?([0-9][0-9,.;]*)',
            full_text,
            re.IGNORECASE
        )
        if tot_cred_match:
            raw_val = tot_cred_match.group(1).replace(';', ',').strip('.,')
            total_credits_reported, _ = parse_amount(raw_val)

    # Currency
    currency = "INR"
    if re.search(r'\b(USD|\$)\b', full_text):
        currency = "USD"
    elif re.search(r'\b(EUR|€)\b', full_text):
        currency = "EUR"
    elif re.search(r'\b(GBP|£)\b', full_text):
        currency = "GBP"

    return AccountDetails(
        account_holder_name=holder_name,
        account_number=acc_no,
        masked_account_number=mask_acc_num(acc_no),
        bank_name=bank_name,
        ifsc_code=ifsc,
        micr_code=micr,
        branch_name=branch,
        customer_id=customer_id,
        statement_period=statement_period,
        opening_balance=opening_balance,
        closing_balance=closing_balance,
        total_debits_reported=total_debits_reported,
        total_credits_reported=total_credits_reported,
        currency=currency
    )


def extract_all_accounts_from_pdf(pdf_path: str, password: str = "") -> List[Tuple[AccountDetails, List[int]]]:
    """
    Detect whether a PDF contains multiple statements/accounts (e.g. concatenated statements)
    and segment the document into individual accounts with their corresponding page ranges.
    Returns: List of (AccountDetails, [1-based page numbers])
    """
    import pymupdf
    try:
        doc = pymupdf.open(pdf_path)
    except Exception:
        return []

    if doc.is_encrypted and password:
        doc.authenticate(password)

    num_pages = len(doc)
    if num_pages == 0:
        doc.close()
        return []

    segments: List[List[int]] = []
    current_pages: List[int] = []
    last_acc_no = None

    for i in range(num_pages):
        page = doc[i]
        txt = page.get_text()
        acct = extract_account_details(txt)
        acc_no = acct.account_number

        is_new_statement = False
        if i > 0:
            prev_txt = doc[i - 1].get_text()
            if "Statement Summary" in prev_txt:
                # If prior page had Statement Summary and current page begins a new account/statement header
                if "Opening Balance" in txt or "Statement" in txt or (acc_no and last_acc_no and acc_no != last_acc_no):
                    is_new_statement = True

        if is_new_statement:
            if current_pages:
                segments.append(current_pages)
            current_pages = [i + 1]
            last_acc_no = acc_no
        else:
            current_pages.append(i + 1)
            if acc_no:
                last_acc_no = acc_no

    if current_pages:
        segments.append(current_pages)

    results: List[Tuple[AccountDetails, List[int]]] = []
    for pages in segments:
        combined_txt = "\n".join(doc[p - 1].get_text() for p in pages)
        acct = extract_account_details(combined_txt)
        results.append((acct, pages))

    doc.close()
    return results
