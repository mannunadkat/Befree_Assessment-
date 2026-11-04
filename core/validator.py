"""Balance reconciliation and auto-repair engine for bank statements."""

from typing import List, Optional, Tuple
from core.models import Transaction, ValidationReport, ValidationIssue


EPSILON = 0.05


def reconcile_and_repair_transactions(
    transactions: List[Transaction],
    opening_balance: Optional[float] = None,
    closing_balance: Optional[float] = None,
    total_debits_reported: Optional[float] = None,
    total_credits_reported: Optional[float] = None
) -> Tuple[List[Transaction], ValidationReport]:
    """
    Validate running balance across transactions:
    balance[i-1] + credit[i] - debit[i] == balance[i]
    Applies auto-repair for:
    - Swapped debit / credit columns
    - OCR misread digit in amounts using the balance equation
    Generates a full validation report.
    """
    if not transactions:
        return [], ValidationReport(
            total_rows=0,
            ok_rows=0,
            repaired_rows=0,
            mismatch_rows=0,
            opening_balance=opening_balance,
            closing_balance=closing_balance,
            calculated_closing_balance=opening_balance,
            total_debits=0.0,
            total_credits=0.0,
            is_reconciled=True if opening_balance == closing_balance else False,
            discrepancy=0.0,
            issues=[]
        )

    issues: List[ValidationIssue] = []
    ok_count = 0
    repaired_count = 0
    mismatch_count = 0

    # Determine initial anchor balance
    prev_balance: Optional[float] = opening_balance if opening_balance is not None else (transactions[0].balance if transactions else None)

    for i, txn in enumerate(transactions):
        # Current values
        cur_debit = txn.debit or 0.0
        cur_credit = txn.credit or 0.0
        actual_bal = txn.balance

        # If balance is None on this row or previous row, running balance math is not applicable
        if actual_bal is None or prev_balance is None:
            txn.validation_status = "OK"
            ok_count += 1
            if actual_bal is not None:
                prev_balance = actual_bal
            continue

        # For the very first row, if opening_balance is present:
        if i == 0 and opening_balance is not None:
            expected_bal = prev_balance + cur_credit - cur_debit
        elif i == 0:
            # No opening balance provided; anchor on first txn balance
            txn.validation_status = "OK"
            ok_count += 1
            prev_balance = actual_bal
            continue
        else:
            expected_bal = prev_balance + cur_credit - cur_debit

        diff = round(actual_bal - expected_bal, 2)

        if abs(diff) < EPSILON:
            # Case 1: Perfect match
            txn.validation_status = "OK"
            ok_count += 1
            prev_balance = actual_bal
        else:
            # Mismatch detected! Attempt auto-repairs
            repaired = False

            # Check Auto-repair 0: Recombine split decimal across Debit and Credit
            if cur_debit > 0 and cur_credit > 0:
                # Case 0A: Debit has integer and Credit has decimal (e.g. 1250 and 0.50, or 1250 and 50)
                recombined_debit = cur_debit + (cur_credit if cur_credit < 1.0 else cur_credit / 100.0)
                if abs(actual_bal - (prev_balance - recombined_debit)) < EPSILON:
                    txn.debit = round(recombined_debit, 2)
                    txn.credit = None
                    txn.validation_status = "Repaired"
                    txn.validation_note = "Auto-repaired: Recombined split decimal from Credit back into Debit."
                    repaired_count += 1
                    repaired = True
                    prev_balance = actual_bal
                    issues.append(ValidationIssue(
                        transaction_id=txn.id,
                        row_index=i + 1,
                        page=txn.page,
                        issue_type="digit_repair",
                        expected_balance=expected_bal,
                        actual_balance=actual_bal,
                        description=f"Amount was split across Debit ({cur_debit}) and Credit ({cur_credit}).",
                        auto_repaired=True,
                        repair_details=f"Recombined into single Debit amount {txn.debit}."
                    ))

                # Case 0B: Credit has integer and Debit has decimal
                if not repaired:
                    recombined_credit = cur_credit + (cur_debit if cur_debit < 1.0 else cur_debit / 100.0)
                    if abs(actual_bal - (prev_balance + recombined_credit)) < EPSILON:
                        txn.credit = round(recombined_credit, 2)
                        txn.debit = None
                        txn.validation_status = "Repaired"
                        txn.validation_note = "Auto-repaired: Recombined split decimal from Debit back into Credit."
                        repaired_count += 1
                        repaired = True
                        prev_balance = actual_bal
                        issues.append(ValidationIssue(
                            transaction_id=txn.id,
                            row_index=i + 1,
                            page=txn.page,
                            issue_type="digit_repair",
                            expected_balance=expected_bal,
                            actual_balance=actual_bal,
                            description=f"Amount was split across Credit ({cur_credit}) and Debit ({cur_debit}).",
                            auto_repaired=True,
                            repair_details=f"Recombined into single Credit amount {txn.credit}."
                        ))

            # Check Auto-repair 1: Swapped Debit and Credit columns
            swapped_bal = prev_balance - cur_credit + cur_debit
            if abs(actual_bal - swapped_bal) < EPSILON:
                # Swap columns
                txn.debit, txn.credit = (txn.credit, txn.debit)
                txn.validation_status = "Repaired"
                txn.validation_note = "Auto-repaired: Swapped Debit and Credit columns to restore balance."
                repaired_count += 1
                repaired = True
                prev_balance = actual_bal
                issues.append(ValidationIssue(
                    transaction_id=txn.id,
                    row_index=i + 1,
                    page=txn.page,
                    issue_type="swapped_columns",
                    expected_balance=expected_bal,
                    actual_balance=actual_bal,
                    description="Debit and Credit values were swapped.",
                    auto_repaired=True,
                    repair_details=f"Swapped Debit {cur_debit} and Credit {cur_credit}"
                ))

            # Check Auto-repair 2: Misread digit in Debit or Credit using balance delta
            if not repaired:
                delta = round(actual_bal - prev_balance, 2)
                # If balance decreased and a debit is present
                if delta < 0 and txn.debit is not None and txn.debit > 0:
                    inferred_debit = round(abs(delta), 2)
                    str_cur = str(cur_debit)
                    str_inf = str(inferred_debit)
                    if abs(len(str_cur) - len(str_inf)) <= 1:
                        common_digits = sum(1 for c in str_cur if c in str_inf)
                        if common_digits >= max(2, len(str_cur) - 1):
                            old_amt = txn.debit
                            txn.debit = inferred_debit
                            txn.credit = None
                            txn.validation_status = "Repaired"
                            txn.validation_note = f"Auto-repaired misread debit from {old_amt} to {inferred_debit}."
                            repaired_count += 1
                            repaired = True
                            prev_balance = actual_bal
                            issues.append(ValidationIssue(
                                transaction_id=txn.id,
                                row_index=i + 1,
                                page=txn.page,
                                issue_type="digit_repair",
                                expected_balance=expected_bal,
                                actual_balance=actual_bal,
                                description=f"Misread debit amount {old_amt}.",
                                auto_repaired=True,
                                repair_details=f"Corrected debit to {inferred_debit} based on balance delta."
                            ))
                elif delta > 0 and txn.credit is not None and txn.credit > 0:
                    inferred_credit = round(delta, 2)
                    str_cur = str(cur_credit)
                    str_inf = str(inferred_credit)
                    if abs(len(str_cur) - len(str_inf)) <= 1:
                        common_digits = sum(1 for c in str_cur if c in str_inf)
                        if common_digits >= max(2, len(str_cur) - 1):
                            old_amt = txn.credit
                            txn.credit = inferred_credit
                            txn.debit = None
                            txn.validation_status = "Repaired"
                            txn.validation_note = f"Auto-repaired misread credit from {old_amt} to {inferred_credit}."
                            repaired_count += 1
                            repaired = True
                            prev_balance = actual_bal
                            issues.append(ValidationIssue(
                                transaction_id=txn.id,
                                row_index=i + 1,
                                page=txn.page,
                                issue_type="digit_repair",
                                expected_balance=expected_bal,
                                actual_balance=actual_bal,
                                description=f"Misread credit amount {old_amt}.",
                                auto_repaired=True,
                                repair_details=f"Corrected credit to {inferred_credit} based on balance delta."
                            ))

            # Case 3: Could not auto-repair
            if not repaired:
                txn.validation_status = "Mismatch"
                txn.validation_note = f"Balance mismatch: Expected {expected_bal:,.2f}, Found {actual_bal:,.2f}."
                mismatch_count += 1
                # Forward actual balance for subsequent rows
                prev_balance = actual_bal
                issues.append(ValidationIssue(
                    transaction_id=txn.id,
                    row_index=i + 1,
                    page=txn.page,
                    issue_type="balance_mismatch",
                    expected_balance=expected_bal,
                    actual_balance=actual_bal,
                    description=f"Discrepancy of {abs(diff):,.2f} between calculated balance and statement balance.",
                    auto_repaired=False,
                    repair_details=None
                ))

    # Calculate overall reconciliation
    if total_debits_reported is not None and total_credits_reported is not None:
        total_debits = total_debits_reported
        total_credits = total_credits_reported
    else:
        total_debits = sum((t.debit or 0.0) for t in transactions)
        total_credits = sum((t.credit or 0.0) for t in transactions)

    if opening_balance is not None:
        start_anchor = opening_balance
    elif transactions and transactions[0].balance is not None:
        start_anchor = transactions[0].balance + (transactions[0].debit or 0.0) - (transactions[0].credit or 0.0)
    else:
        start_anchor = 0.0

    calculated_closing = round(start_anchor + total_credits - total_debits, 2)

    if closing_balance is not None:
        target_closing = closing_balance
    elif transactions and transactions[-1].balance is not None:
        target_closing = transactions[-1].balance
    else:
        target_closing = calculated_closing

    discrepancy = round(abs(calculated_closing - target_closing), 2)
    is_reconciled = (discrepancy < EPSILON) and (mismatch_count == 0 or (total_debits_reported is not None and discrepancy < EPSILON))

    report = ValidationReport(
        total_rows=len(transactions),
        ok_rows=ok_count,
        repaired_rows=repaired_count,
        mismatch_rows=mismatch_count,
        opening_balance=opening_balance,
        closing_balance=closing_balance,
        calculated_closing_balance=calculated_closing,
        total_debits=round(total_debits, 2),
        total_credits=round(total_credits, 2),
        is_reconciled=is_reconciled,
        discrepancy=discrepancy,
        issues=issues
    )

    return transactions, report
