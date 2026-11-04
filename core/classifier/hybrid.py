"""Hybrid classifier orchestrator: Overrides -> Rules -> ML -> Uncategorized."""

import os
import csv
from typing import Optional, Dict
from core.models import Transaction
from core.classifier.rules import classify_by_rules, detect_payment_mode, extract_counterparty
from core.classifier.ml_model import classify_by_ml


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
OVERRIDES_FILE = os.path.join(DATA_DIR, "user_overrides.csv")

_overrides_cache: Optional[Dict[str, str]] = None


def load_overrides() -> Dict[str, str]:
    global _overrides_cache
    if _overrides_cache is not None:
        return _overrides_cache

    _overrides_cache = {}
    if os.path.exists(OVERRIDES_FILE):
        try:
            with open(OVERRIDES_FILE, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    desc_key = row.get("description", "").strip().lower()
                    cat = row.get("category", "").strip()
                    if desc_key and cat:
                        _overrides_cache[desc_key] = cat
        except Exception:
            pass
    return _overrides_cache


def record_user_override(description: str, category: str):
    """Save user manual classification override and update in-memory cache."""
    global _overrides_cache
    os.makedirs(DATA_DIR, exist_ok=True)
    clean_desc = description.strip()

    file_exists = os.path.exists(OVERRIDES_FILE)
    with open(OVERRIDES_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["description", "category"])
        if not file_exists:
            writer.writeheader()
        writer.writerow({"description": clean_desc, "category": category})

    if _overrides_cache is None:
        _overrides_cache = {}
    _overrides_cache[clean_desc.lower()] = category


INFLOW_ONLY_CATEGORIES = {
    "Salary/Income", "Cash Deposit", "Interest Earned", "Refund/Reversal", "Transfer In", "Interest"
}
OUTFLOW_ONLY_CATEGORIES = {
    "EMI/Loan", "Rent", "Groceries", "Food & Dining", "Utilities & Bills", "Utilities",
    "Fuel", "Travel & Transport", "Shopping", "Entertainment/Subscriptions", "Healthcare",
    "Mobile/Internet/DTH Recharge", "ATM Withdrawal", "Transfer Out (Person)"
}


def classify_transaction(
    txn: Transaction,
    confidence_threshold: float = 0.55
) -> Transaction:
    """
    Classify a single transaction using the hybrid non-LLM pipeline.
    Populates: category, category_confidence, classification_source, payment_mode, counterparty.
    """
    desc = txn.description or ""
    desc_lower = desc.strip().lower()

    # Step 1: Detect payment mode and counterparty
    if not txn.payment_mode or txn.payment_mode == "Other":
        txn.payment_mode = detect_payment_mode(desc)
    if not txn.counterparty:
        txn.counterparty = extract_counterparty(desc)

    # Step 2: Check manual user overrides
    overrides = load_overrides()
    if desc_lower in overrides:
        txn.category = overrides[desc_lower]
        txn.category_confidence = 1.0
        txn.classification_source = "manual"
        return txn

    # Preserve pre-existing manual/ground-truth classification from imports
    if txn.classification_source == "manual" and txn.category and txn.category != "Uncategorized":
        return txn

    # Step 3: Heuristic rules engine
    rule_cat, rule_conf, rule_counterparty, rule_mode = classify_by_rules(
        description=desc,
        debit=txn.debit,
        credit=txn.credit
    )
    if rule_counterparty and not txn.counterparty:
        txn.counterparty = rule_counterparty
    if rule_mode != "Other" and txn.payment_mode == "Other":
        txn.payment_mode = rule_mode

    # Direction consistency flags
    is_pure_debit = txn.debit is not None and txn.debit > 0 and (not txn.credit or txn.credit == 0)
    is_pure_credit = txn.credit is not None and txn.credit > 0 and (not txn.debit or txn.debit == 0)

    # If rule matched with high priority/confidence, prefer rule
    if rule_cat and rule_conf >= 0.85:
        txn.category = rule_cat
        txn.category_confidence = rule_conf
        txn.classification_source = "rule"
        return txn

    # Step 4: Classical ML model with high-accuracy subword features
    ml_cat, ml_conf = classify_by_ml(desc)

    # Direction sanity check: debits cannot be salary/deposit; credits cannot be rent/groceries
    ml_valid = True
    if is_pure_debit and ml_cat in INFLOW_ONLY_CATEGORIES:
        ml_valid = False
    elif is_pure_credit and ml_cat in OUTFLOW_ONLY_CATEGORIES:
        ml_valid = False

    # Prefer ML if confident and directionally valid
    if ml_valid and ml_conf >= min(0.20, confidence_threshold) and ml_cat != "Uncategorized":
        txn.category = ml_cat
        txn.category_confidence = ml_conf
        txn.classification_source = "ml"
        return txn

    if rule_cat:
        txn.category = rule_cat
        txn.category_confidence = rule_conf
        txn.classification_source = "rule"
        return txn

    # Step 5: Fallback
    txn.category = "Uncategorized"
    txn.category_confidence = 0.0
    txn.classification_source = "rule"
    return txn
