"""Recurring transaction detection based on counterparty, amount similarity, and cadence."""

from typing import List, Dict
from datetime import datetime
from collections import defaultdict
from core.models import Transaction


def detect_recurring_transactions(transactions: List[Transaction]) -> List[Transaction]:
    """
    Identifies recurring transactions:
    - Same counterparty (or similar description key)
    - Similar amount (within 15% tolerance or exact)
    - Roughly monthly interval (22 to 38 days) or quarterly (80 to 100 days)
    """
    if len(transactions) < 2:
        return transactions

    # Group by key: (counterparty or simplified description prefix, is_debit)
    groups: Dict[tuple, List[Transaction]] = defaultdict(list)

    for txn in transactions:
        amt = txn.debit if txn.debit is not None else (txn.credit or 0.0)
        if amt <= 0:
            continue
        is_debit = txn.debit is not None

        # Key determination
        if txn.counterparty:
            key_name = txn.counterparty.lower()
        else:
            # First two words of description
            words = txn.description.lower().split()
            key_name = " ".join(words[:2]) if len(words) >= 2 else (words[0] if words else "other")

        groups[(key_name, is_debit)].append(txn)

    # Analyze intervals within each group
    for (key_name, is_debit), items in groups.items():
        if len(items) < 2:
            # If explicit recurring subscription like Netflix, Spotify, SIP, Rent, EMI
            # even a single one in a 1-month statement can be flagged if recognized:
            for itm in items:
                desc_lower = itm.description.lower()
                if any(k in desc_lower for k in ["netflix", "spotify", "sip", "emi", "rent", "broadband", "insurance", "recharge"]):
                    itm.is_recurring = True
            continue

        # Sort chronologically
        try:
            sorted_items = sorted(items, key=lambda t: datetime.strptime(t.date, "%Y-%m-%d"))
        except Exception:
            sorted_items = items

        for i in range(len(sorted_items)):
            amt_i = sorted_items[i].debit if is_debit else sorted_items[i].credit
            date_i = None
            try:
                date_i = datetime.strptime(sorted_items[i].date, "%Y-%m-%d")
            except Exception:
                pass

            for j in range(i + 1, len(sorted_items)):
                amt_j = sorted_items[j].debit if is_debit else sorted_items[j].credit
                date_j = None
                try:
                    date_j = datetime.strptime(sorted_items[j].date, "%Y-%m-%d")
                except Exception:
                    pass

                # Check amount similarity (within 15%)
                if amt_i and amt_j:
                    max_amt = max(amt_i, amt_j)
                    if abs(amt_i - amt_j) / max_amt <= 0.15:
                        if date_i and date_j:
                            days = abs((date_j - date_i).days)
                            # Monthly (~25-35 days), Bi-weekly (~12-16 days), or Quarterly (~80-100 days)
                            if 20 <= days <= 40 or 12 <= days <= 16 or 80 <= days <= 100:
                                sorted_items[i].is_recurring = True
                                sorted_items[j].is_recurring = True

    return transactions
