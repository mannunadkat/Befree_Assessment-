"""Heuristic rule-based transaction classifier and metadata extractor."""

import os
import json
import re
from typing import Tuple, Optional, Dict, Any


KEYWORDS_PATH = os.path.join(os.path.dirname(__file__), "keywords.json")

_config_cache: Optional[Dict[str, Any]] = None


def get_config() -> Dict[str, Any]:
    global _config_cache
    if _config_cache is None:
        with open(KEYWORDS_PATH, "r", encoding="utf-8") as f:
            _config_cache = json.load(f)
    return _config_cache


def detect_payment_mode(description: str) -> str:
    """Detect payment instrument/mode from narration string."""
    config = get_config()
    desc_lower = description.lower()

    for mode, patterns in config.get("payment_modes", {}).items():
        for pat in patterns:
            if re.search(pat, desc_lower):
                return mode
    return "Other"


def extract_counterparty(description: str) -> Optional[str]:
    """Extract recognized merchant or counterparty name."""
    config = get_config()
    desc_lower = description.lower()

    # 1. Match known merchant dictionary
    for merchant_name, aliases in config.get("merchants", {}).items():
        for alias in aliases:
            if re.search(rf'\b{re.escape(alias)}\b', desc_lower):
                return merchant_name

    # 2. Extract from standard UPI narration: UPI/<ref>/<Name>/<vpa>
    upi_match = re.search(r'upi/[^/]+/([^/]+)/', description, re.IGNORECASE)
    if upi_match:
        cand = upi_match.group(1).strip()
        if len(cand) >= 2 and not cand.isdigit():
            return cand

    # 3. Extract from NEFT/IMPS: NEFT CR-<IFSC>-<NAME>-<PURPOSE>
    neft_match = re.search(r'(?:neft|imps)[-\s]*(?:cr|dr)[-\s]*[a-z0-9]+[-\s]+([a-z\s]+?)(?:-[a-z\s]+|$)', description, re.IGNORECASE)
    if neft_match:
        cand = neft_match.group(1).strip()
        if len(cand) >= 3:
            return cand

    return None


def classify_by_rules(
    description: str,
    debit: Optional[float] = None,
    credit: Optional[float] = None
) -> Tuple[Optional[str], float, Optional[str], str]:
    """
    Classify transaction using deterministic regex rules and transaction direction.
    Returns:
    (category, confidence, counterparty, payment_mode)
    """
    config = get_config()
    desc_lower = description.lower()
    is_credit = credit is not None and credit > 0
    is_debit = debit is not None and debit > 0

    mode = detect_payment_mode(description)
    counterparty = extract_counterparty(description)

    # Sort rules by priority descending
    rules = sorted(config.get("rules", []), key=lambda r: r.get("priority", 0), reverse=True)

    for rule in rules:
        direction = rule.get("direction", "any")
        if direction == "credit" and not is_credit:
            continue
        if direction == "debit" and not is_debit:
            continue

        pattern = rule.get("regex", "")
        if re.search(pattern, desc_lower):
            category = rule["category"]
            confidence = min(1.0, 0.70 + (rule.get("priority", 50) / 100.0) * 0.30)
            return category, round(confidence, 2), counterparty, mode

    return None, 0.0, counterparty, mode
