"""Tests for Account Parser."""

from core.account_parser import extract_account_details, mask_acc_num


SAMPLE_TEXT = """
HDFC BANK LIMITED
Account Statement - Savings Account

Customer Name: ARJUN MEHTA        Account No: 50100293847561
Customer ID: 98271625              IFSC Code: HDFC0000240
Branch: KORAMANGALA 4TH BLOCK, BANGALORE  MICR Code: 560240003
Statement Period: 01/01/2024 to 31/01/2024 Currency: INR
Opening Balance: 1,00,000.00       Closing Balance: 1,82,210.50
"""


def test_extract_account_details():
    acc = extract_account_details(SAMPLE_TEXT)
    assert acc.bank_name == "HDFC Bank"
    assert acc.account_number == "50100293847561"
    assert acc.masked_account_number == "XXXXXXXXXX7561"
    assert acc.account_holder_name == "ARJUN MEHTA"
    assert acc.ifsc_code == "HDFC0000240"
    assert acc.micr_code == "560240003"
    assert acc.opening_balance == 100000.00
    assert acc.closing_balance == 182210.50
    assert acc.currency == "INR"


def test_mask_acc_num():
    assert mask_acc_num("1234567890") == "XXXXXX7890"
    assert mask_acc_num("123") == "XXXX"
