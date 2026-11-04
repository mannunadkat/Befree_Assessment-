"""Tests for Classification Engine (Rules, ML, Overrides) and Recurring Detector."""

import os
import pytest
from core.models import Transaction
from core.classifier.rules import classify_by_rules, detect_payment_mode, extract_counterparty
from core.classifier.ml_model import classify_by_ml
from core.classifier.hybrid import classify_transaction, record_user_override
from core.recurring import detect_recurring_transactions


def test_payment_mode_detection():
    assert detect_payment_mode("UPI/400192837461/Swiggy/swiggy@axis") == "UPI"
    assert detect_payment_mode("NEFT CR-HDFC0000001-SALARY") == "NEFT"
    assert detect_payment_mode("ATM WDL CASH HDFC ATM KORAMANGALA") == "ATM"
    assert detect_payment_mode("POS DEBIT BIGBASKET INDIRANAGAR") == "POS"
    assert detect_payment_mode("ACH/GROWW/SIP-MUTUAL-FUND") == "ECS/NACH"


def test_counterparty_extraction():
    assert extract_counterparty("UPI/400192837461/Swiggy/swiggy@axis") == "Swiggy"
    assert extract_counterparty("POS DEBIT BIGBASKET INDIRANAGAR") == "BigBasket"
    assert extract_counterparty("NETFLIX MUMBAI IN RET 99281729") == "Netflix"
    assert extract_counterparty("ZERODHA BROKING LTD EQUITY") == "Zerodha"


def test_rule_classification():
    cat, conf, cp, mode = classify_by_rules("SALARY CREDIT FOR DEC 2023 ACME TECH", credit=85000.0)
    assert cat == "Salary/Income"
    assert conf > 0.8

    cat2, conf2, _, _ = classify_by_rules("UPI/400192837461/Swiggy/swiggy@axis", debit=489.0)
    assert cat2 == "Food & Dining"

    # Same merchant on credit should classify as Refund/Reversal
    cat3, conf3, _, _ = classify_by_rules("REFUND/AMZN-MKTPLACE-IN/49281726", credit=1899.0)
    assert cat3 == "Refund/Reversal"


def test_ml_classification():
    cat, prob = classify_by_ml("Monthly wages disbursement for employees")
    assert cat == "Salary/Income"
    assert prob > 0.50

    cat2, prob2 = classify_by_ml("Starbucks Frappuccino and roasted coffee beans")
    assert cat2 == "Food & Dining"
    assert prob2 > 0.50


def test_user_override():
    txn = Transaction(
        date="2024-01-01",
        description="SPECIAL CUSTOM VENDOR XYZ PAYMENT",
        debit=1500.0,
        balance=5000.0
    )
    # Record manual override
    record_user_override("SPECIAL CUSTOM VENDOR XYZ PAYMENT", "Consulting & Legal")
    classified = classify_transaction(txn)
    assert classified.category == "Consulting & Legal"
    assert classified.classification_source == "manual"
    assert classified.category_confidence == 1.0


def test_recurring_transactions():
    txns = [
        Transaction(date="2024-01-15", description="NETFLIX MUMBAI IN RET 99281729", debit=649.0, balance=9351.0),
        Transaction(date="2024-02-15", description="NETFLIX MUMBAI IN RET 99281730", debit=649.0, balance=8702.0),
    ]
    detected = detect_recurring_transactions(txns)
    assert detected[0].is_recurring is True
    assert detected[1].is_recurring is True
