"""Export engine: Generates structured CSV and styled multi-sheet Excel with native charts."""

import io
import csv
from typing import List, Optional
from collections import defaultdict
import xlsxwriter
from core.models import AccountDetails, Transaction, ValidationReport


def export_to_csv(transactions: List[Transaction], output_path: Optional[str] = None) -> bytes:
    """Generate CSV containing all extracted transaction details and classification."""
    output = io.StringIO()
    fieldnames = [
        "date", "value_date", "description", "ref_no", "payment_mode",
        "counterparty", "debit", "credit", "balance", "category",
        "category_confidence", "classification_source", "is_recurring",
        "validation_status", "source_file", "page"
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    for t in transactions:
        writer.writerow({
            "date": t.date,
            "value_date": t.value_date or t.date,
            "description": t.description,
            "ref_no": t.ref_no or "",
            "payment_mode": t.payment_mode or "Other",
            "counterparty": t.counterparty or "",
            "debit": t.debit if t.debit is not None else "",
            "credit": t.credit if t.credit is not None else "",
            "balance": t.balance,
            "category": t.category,
            "category_confidence": round(t.category_confidence, 2),
            "classification_source": t.classification_source,
            "is_recurring": "Yes" if t.is_recurring else "No",
            "validation_status": t.validation_status,
            "source_file": t.source_file,
            "page": t.page
        })

    csv_data = output.getvalue().encode("utf-8")
    if output_path:
        with open(output_path, "wb") as f:
            f.write(csv_data)
    return csv_data


def export_to_excel(
    account: AccountDetails,
    transactions: List[Transaction],
    validation: ValidationReport,
    output_path: Optional[str] = None
) -> bytes:
    """
    Generate professional multi-sheet Excel workbook:
    1. Account Details
    2. Transactions (frozen headers, autofilters, red debit / green credit, currency formats)
    3. Category Summary (totals, counts, native Excel donut/pie chart)
    4. Monthly Summary (income vs expense bar chart)
    5. Validation Report (reconciliation status, repair log)
    """
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})

    # Styling formats
    fmt_header = workbook.add_format({
        'bold': True,
        'bg_color': '#1E293B',
        'font_color': '#FFFFFF',
        'border': 1,
        'align': 'center',
        'valign': 'vcenter'
    })
    fmt_title = workbook.add_format({
        'bold': True,
        'font_size': 14,
        'font_color': '#0F172A',
        'bottom': 2
    })
    fmt_bold = workbook.add_format({'bold': True})
    fmt_label = workbook.add_format({'bold': True, 'bg_color': '#F1F5F9', 'border': 1})
    fmt_val = workbook.add_format({'border': 1})

    fmt_date = workbook.add_format({'num_format': 'yyyy-mm-dd', 'align': 'center', 'border': 1})
    fmt_curr = workbook.add_format({'num_format': '#,##0.00', 'border': 1})
    fmt_debit = workbook.add_format({'num_format': '#,##0.00', 'font_color': '#E11D48', 'border': 1})
    fmt_credit = workbook.add_format({'num_format': '#,##0.00', 'font_color': '#10B981', 'border': 1})
    fmt_cell = workbook.add_format({'border': 1})
    fmt_center = workbook.add_format({'align': 'center', 'border': 1})

    # ----------------------------------------------------
    # Sheet 1: Account Details
    # ----------------------------------------------------
    ws_acc = workbook.add_worksheet("Account Details")
    ws_acc.set_column('A:A', 24)
    ws_acc.set_column('B:B', 35)

    ws_acc.write('A1', 'Bank Statement Summary', fmt_title)
    acc_rows = [
        ("Bank Name", account.bank_name or "N/A"),
        ("Account Holder", account.account_holder_name or "N/A"),
        ("Account Number", account.masked_account_number or account.account_number or "N/A"),
        ("Customer ID", account.customer_id or "N/A"),
        ("IFSC Code", account.ifsc_code or "N/A"),
        ("MICR Code", account.micr_code or "N/A"),
        ("Branch", account.branch_name or "N/A"),
        ("Statement Period", account.statement_period or "N/A"),
        ("Currency", account.currency or "INR"),
        ("Opening Balance", f"{account.opening_balance:,.2f}" if account.opening_balance is not None else "N/A"),
        ("Closing Balance", f"{account.closing_balance:,.2f}" if account.closing_balance is not None else "N/A"),
        ("Document Type", account.pdf_type.capitalize()),
    ]
    for r_idx, (lbl, val) in enumerate(acc_rows, start=2):
        ws_acc.write(r_idx, 0, lbl, fmt_label)
        ws_acc.write(r_idx, 1, val, fmt_val)

    # ----------------------------------------------------
    # Sheet 2: Transactions
    # ----------------------------------------------------
    ws_tx = workbook.add_worksheet("Transactions")
    ws_tx.freeze_panes(1, 0)

    headers = [
        "Date", "Value Date", "Description", "Ref No", "Mode",
        "Counterparty", "Debit", "Credit", "Balance", "Category",
        "Confidence", "Source", "Recurring", "Validation", "File", "Page"
    ]
    for c_idx, h in enumerate(headers):
        ws_tx.write(0, c_idx, h, fmt_header)

    for r_idx, t in enumerate(transactions, start=1):
        ws_tx.write(r_idx, 0, t.date, fmt_date)
        ws_tx.write(r_idx, 1, t.value_date or t.date, fmt_date)
        ws_tx.write(r_idx, 2, t.description, fmt_cell)
        ws_tx.write(r_idx, 3, t.ref_no or "", fmt_cell)
        ws_tx.write(r_idx, 4, t.payment_mode or "Other", fmt_center)
        ws_tx.write(r_idx, 5, t.counterparty or "", fmt_cell)

        if t.debit is not None:
            ws_tx.write_number(r_idx, 6, t.debit, fmt_debit)
        else:
            ws_tx.write_blank(r_idx, 6, None, fmt_cell)

        if t.credit is not None:
            ws_tx.write_number(r_idx, 7, t.credit, fmt_credit)
        else:
            ws_tx.write_blank(r_idx, 7, None, fmt_cell)

        ws_tx.write_number(r_idx, 8, t.balance, fmt_curr)
        ws_tx.write(r_idx, 9, t.category, fmt_cell)
        ws_tx.write_number(r_idx, 10, round(t.category_confidence, 2), fmt_center)
        ws_tx.write(r_idx, 11, t.classification_source, fmt_center)
        ws_tx.write(r_idx, 12, "Yes" if t.is_recurring else "No", fmt_center)
        ws_tx.write(r_idx, 13, t.validation_status, fmt_center)
        ws_tx.write(r_idx, 14, t.source_file, fmt_cell)
        ws_tx.write_number(r_idx, 15, t.page, fmt_center)

    ws_tx.autofilter(0, 0, len(transactions), len(headers) - 1)
    ws_tx.set_column('A:B', 12)
    ws_tx.set_column('C:C', 38)
    ws_tx.set_column('D:D', 15)
    ws_tx.set_column('E:E', 12)
    ws_tx.set_column('F:F', 20)
    ws_tx.set_column('G:I', 15)
    ws_tx.set_column('J:J', 24)
    ws_tx.set_column('K:N', 12)

    # ----------------------------------------------------
    # Sheet 3: Category Summary (with Native Chart)
    # ----------------------------------------------------
    ws_cat = workbook.add_worksheet("Category Summary")
    ws_cat.write('A1', 'Category', fmt_header)
    ws_cat.write('B1', 'Total Debit (Expenses)', fmt_header)
    ws_cat.write('C1', 'Total Credit (Income)', fmt_header)
    ws_cat.write('D1', 'Txn Count', fmt_header)

    cat_debits = defaultdict(float)
    cat_credits = defaultdict(float)
    cat_counts = defaultdict(int)

    for t in transactions:
        cat_debits[t.category] += (t.debit or 0.0)
        cat_credits[t.category] += (t.credit or 0.0)
        cat_counts[t.category] += 1

    all_cats = sorted(set(list(cat_debits.keys()) + list(cat_credits.keys())))
    for c_idx, c_name in enumerate(all_cats, start=1):
        ws_cat.write(c_idx, 0, c_name, fmt_cell)
        ws_cat.write_number(c_idx, 1, round(cat_debits[c_name], 2), fmt_curr)
        ws_cat.write_number(c_idx, 2, round(cat_credits[c_name], 2), fmt_curr)
        ws_cat.write_number(c_idx, 3, cat_counts[c_name], fmt_center)

    ws_cat.set_column('A:A', 26)
    ws_cat.set_column('B:C', 22)
    ws_cat.set_column('D:D', 12)

    # Add Native Excel Pie Chart for Category Spending
    if len(all_cats) > 0:
        chart_cat = workbook.add_chart({'type': 'pie'})
        chart_cat.add_series({
            'name': 'Spending by Category',
            'categories': ['Category Summary', 1, 0, len(all_cats), 0],
            'values': ['Category Summary', 1, 1, len(all_cats), 1],
        })
        chart_cat.set_title({'name': 'Spending by Category'})
        chart_cat.set_style(10)
        ws_cat.insert_chart('F2', chart_cat, {'x_scale': 1.2, 'y_scale': 1.2})

    # ----------------------------------------------------
    # Sheet 4: Monthly Summary (Income vs Expense)
    # ----------------------------------------------------
    ws_mon = workbook.add_worksheet("Monthly Summary")
    ws_mon.write('A1', 'Month', fmt_header)
    ws_mon.write('B1', 'Total Income', fmt_header)
    ws_mon.write('C1', 'Total Expenses', fmt_header)
    ws_mon.write('D1', 'Net Cashflow', fmt_header)

    mon_income = defaultdict(float)
    mon_expense = defaultdict(float)

    for t in transactions:
        m_str = t.date[:7] if len(t.date) >= 7 else "Unknown"
        mon_income[m_str] += (t.credit or 0.0)
        mon_expense[m_str] += (t.debit or 0.0)

    months = sorted(set(list(mon_income.keys()) + list(mon_expense.keys())))
    for m_idx, m_str in enumerate(months, start=1):
        inc = round(mon_income[m_str], 2)
        exp = round(mon_expense[m_str], 2)
        net = round(inc - exp, 2)
        ws_mon.write(m_idx, 0, m_str, fmt_center)
        ws_mon.write_number(m_idx, 1, inc, fmt_credit)
        ws_mon.write_number(m_idx, 2, exp, fmt_debit)
        ws_mon.write_number(m_idx, 3, net, fmt_curr)

    ws_mon.set_column('A:A', 14)
    ws_mon.set_column('B:D', 18)

    # Native Excel Column Chart for Income vs Expense
    if len(months) > 0:
        chart_mon = workbook.add_chart({'type': 'column'})
        chart_mon.add_series({
            'name': 'Income',
            'categories': ['Monthly Summary', 1, 0, len(months), 0],
            'values': ['Monthly Summary', 1, 1, len(months), 1],
            'fill': {'color': '#10B981'}
        })
        chart_mon.add_series({
            'name': 'Expenses',
            'categories': ['Monthly Summary', 1, 0, len(months), 0],
            'values': ['Monthly Summary', 1, 2, len(months), 2],
            'fill': {'color': '#E11D48'}
        })
        chart_mon.set_title({'name': 'Monthly Income vs Expenses'})
        ws_mon.insert_chart('F2', chart_mon, {'x_scale': 1.2, 'y_scale': 1.2})

    # ----------------------------------------------------
    # Sheet 5: Validation Report
    # ----------------------------------------------------
    ws_val = workbook.add_worksheet("Validation Report")
    ws_val.write('A1', 'Reconciliation Summary', fmt_title)
    val_rows = [
        ("Reconciliation Status", "RECONCILED" if validation.is_reconciled else "MISMATCH / UNBALANCED"),
        ("Total Rows Checked", validation.total_rows),
        ("OK Rows", validation.ok_rows),
        ("Auto-Repaired Rows", validation.repaired_rows),
        ("Mismatch Rows", validation.mismatch_rows),
        ("Opening Balance", f"{validation.opening_balance:,.2f}" if validation.opening_balance is not None else "N/A"),
        ("Total Credits (+)", f"{validation.total_credits:,.2f}"),
        ("Total Debits (-)", f"{validation.total_debits:,.2f}"),
        ("Calculated Closing Balance", f"{validation.calculated_closing_balance:,.2f}" if validation.calculated_closing_balance is not None else "N/A"),
        ("Statement Closing Balance", f"{validation.closing_balance:,.2f}" if validation.closing_balance is not None else "N/A"),
        ("Discrepancy", f"{validation.discrepancy:,.2f}"),
    ]
    for r_idx, (lbl, val) in enumerate(val_rows, start=2):
        ws_val.write(r_idx, 0, lbl, fmt_label)
        ws_val.write(r_idx, 1, val, fmt_val)

    # Issue Log table
    if validation.issues:
        start_row = len(val_rows) + 4
        ws_val.write(start_row, 0, "Row", fmt_header)
        ws_val.write(start_row, 1, "Page", fmt_header)
        ws_val.write(start_row, 2, "Issue Type", fmt_header)
        ws_val.write(start_row, 3, "Expected Bal", fmt_header)
        ws_val.write(start_row, 4, "Actual Bal", fmt_header)
        ws_val.write(start_row, 5, "Auto-Repaired?", fmt_header)
        ws_val.write(start_row, 6, "Details", fmt_header)

        for i_idx, issue in enumerate(validation.issues, start=start_row + 1):
            ws_val.write_number(i_idx, 0, issue.row_index, fmt_center)
            ws_val.write_number(i_idx, 1, issue.page, fmt_center)
            ws_val.write(i_idx, 2, issue.issue_type, fmt_cell)
            ws_val.write_number(i_idx, 3, issue.expected_balance, fmt_curr)
            ws_val.write_number(i_idx, 4, issue.actual_balance, fmt_curr)
            ws_val.write(i_idx, 5, "Yes" if issue.auto_repaired else "No", fmt_center)
            ws_val.write(i_idx, 6, issue.repair_details or issue.description, fmt_cell)

    ws_val.set_column('A:B', 28)
    ws_val.set_column('C:G', 20)

    workbook.close()
    excel_bytes = output.getvalue()
    if output_path:
        with open(output_path, "wb") as f:
            f.write(excel_bytes)
    return excel_bytes
