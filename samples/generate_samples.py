"""Synthetic Bank Statement PDF Generator with Ground Truth."""

import os
import json
import random
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import pymupdf  # PyMuPDF
import cv2
import numpy as np


SAMPLES_DIR = os.path.dirname(__file__)


SAMPLE_1_TXNS = [
    {"date": "02/01/2024", "val_date": "02/01/2024", "desc": "UPI/400192837461/Swiggy/swiggy@axis", "ref": "400192837461", "debit": 489.00, "credit": None, "balance": 99511.00, "category": "Food & Dining"},
    {"date": "05/01/2024", "val_date": "05/01/2024", "desc": "ACH/GROWW/SIP-MUTUAL-FUND-29381", "ref": "GROWW29381", "debit": 5000.00, "credit": None, "balance": 94511.00, "category": "Investments/Mutual Funds/SIP"},
    {"date": "10/01/2024", "val_date": "10/01/2024", "desc": "SALARY CREDIT FOR DEC 2023 ACME TECH PVT LTD", "ref": "CMS998811", "debit": None, "credit": 85000.00, "balance": 179511.00, "category": "Salary/Income"},
    {"date": "12/01/2024", "val_date": "12/01/2024", "desc": "UPI/401298471625/Blinkit/blinkit@icici", "ref": "401298471625", "debit": 1250.50, "credit": None, "balance": 178260.50, "category": "Groceries"},
    {"date": "15/01/2024", "val_date": "15/01/2024", "desc": "NETFLIX MUMBAI IN RET 99281729", "ref": "NF9928172", "debit": 649.00, "credit": None, "balance": 177611.50, "category": "Entertainment/Subscriptions"},
    {"date": "18/01/2024", "val_date": "18/01/2024", "desc": "ATM WDL CASH HDFC ATM KORAMANGALA BLR", "ref": "ATM9812", "debit": 4000.00, "credit": None, "balance": 173611.50, "category": "ATM Withdrawal"},
    {"date": "22/01/2024", "val_date": "22/01/2024", "desc": "UPI/402281928371/HPCL FUEL PUMP BLR", "ref": "402281928371", "debit": 2100.00, "credit": None, "balance": 171511.50, "category": "Fuel"},
    {"date": "25/01/2024", "val_date": "25/01/2024", "desc": "REFUND/AMZN-MKTPLACE-IN/49281726", "ref": "AMZ49281", "debit": None, "credit": 1899.00, "balance": 173410.50, "category": "Refund/Reversal"},
    {"date": "28/01/2024", "val_date": "28/01/2024", "desc": "NEFT CR-CITI0000001-RAHUL SHARMA-RENT SHARE", "ref": "NEFT992812", "debit": None, "credit": 12000.00, "balance": 185410.50, "category": "Transfer In"},
    {"date": "30/01/2024", "val_date": "30/01/2024", "desc": "AUTO-DEBIT HDFC ERGO HEALTH INSURANCE", "ref": "INS88192", "debit": 3200.00, "credit": None, "balance": 182210.50, "category": "Insurance"},
]

SAMPLE_2_TXNS = [
    {"date": "03-02-2024", "val_date": "03-02-2024", "desc": "UPI/403482716254/Uber India/uber@axis", "ref": "403482716254", "amount": 420.00, "type": "DR", "balance": 54580.00, "category": "Travel & Transport"},
    {"date": "06-02-2024", "val_date": "06-02-2024", "desc": "POS/BIGBASKET INDIRANAGAR/99281", "ref": "POS99281", "amount": 3450.00, "type": "DR", "balance": 51130.00, "category": "Groceries"},
    {"date": "10-02-2024", "val_date": "10-02-2024", "desc": "SALARY CREDIT - INFOSYS LTD FEB 2024", "ref": "SAL202402", "amount": 92000.00, "type": "CR", "balance": 143130.00, "category": "Salary/Income"},
    {"date": "14-02-2024", "val_date": "14-02-2024", "desc": "UPI/404592837162/ZOMATO RESTAURANT/zomato@hdfc", "ref": "404592837162", "amount": 890.00, "type": "DR", "balance": 142240.00, "category": "Food & Dining"},
    {"date": "18-02-2024", "val_date": "18-02-2024", "desc": "ZERODHA BROKING LTD EQUITY SIP", "ref": "ZERODHA8812", "amount": 10000.00, "type": "DR", "balance": 132240.00, "category": "Stocks"},
    {"date": "21-02-2024", "val_date": "21-02-2024", "desc": "JIO PREPAID RECHARGE 8829102910", "ref": "JIO99182", "amount": 749.00, "type": "DR", "balance": 131491.00, "category": "Mobile/Internet/DTH Recharge"},
    {"date": "25-02-2024", "val_date": "25-02-2024", "desc": "ELECTRICITY BILL BESCOM BANGALORE", "ref": "BESCOM7712", "amount": 2150.00, "type": "DR", "balance": 129341.00, "category": "Utilities & Bills"},
    {"date": "28-02-2024", "val_date": "28-02-2024", "desc": "ANNUAL SMS CHARGES + GST", "ref": "CHG88172", "amount": 59.00, "type": "DR", "balance": 129282.00, "category": "Bank Charges/Fees"},
]

SAMPLE_3_TXNS = [
    {"date": "2024-03-01", "desc": "Amazon.in Payments retail order 402-991827", "ref": "AMZN40299", "amount": -2499.00, "balance": 87501.00, "category": "Shopping"},
    {"date": "2024-03-05", "desc": "HDFC HOME LOAN EMI 992817291", "ref": "EMI99281", "amount": -28500.00, "balance": 59001.00, "category": "EMI/Loan"},
    {"date": "2024-03-10", "desc": "CRED CLUB CREDIT CARD BILL PAYMENT", "ref": "CRED88129", "amount": -14500.00, "balance": 44501.00, "category": "Credit Card Payment"},
    {"date": "2024-03-15", "desc": "CLIENT CONSULTING INVOICE INV-2024-08", "ref": "INV202408", "amount": 65000.00, "balance": 109501.00, "category": "Salary/Income"},
    {"date": "2024-03-20", "desc": "SPOTIFY PREMIUM SUBSCRIPTION", "ref": "SPOT99281", "amount": -179.00, "balance": 109322.00, "category": "Entertainment/Subscriptions"},
    {"date": "2024-03-25", "desc": "APOLLO PHARMACY BANGALORE MEDICINES", "ref": "APOLLO331", "amount": -1420.00, "balance": 107902.00, "category": "Healthcare"},
    {"date": "2024-03-31", "desc": "QUARTERLY SAVINGS INTEREST CREDITED", "ref": "INT2024Q1", "amount": 645.00, "balance": 108547.00, "category": "Interest Earned"},
]

# Multi-page sample with multi-line narrations
SAMPLE_4_TXNS_P1 = [
    {"date": "01/04/2024", "val_date": "01/04/2024", "desc": "HOUSE RENT PAID TO LANDLORD MR ANIL KUMAR VIA NEFT SBIN0001234", "ref": "NEFT001", "debit": 25000.00, "credit": None, "balance": 125000.00, "category": "Rent"},
    {"date": "04/04/2024", "val_date": "04/04/2024", "desc": "UPI/409918273615/Swiggy/swiggy@axisbank\nORDER ID 9928172 LUNCH DELIVERY", "ref": "409918273615", "debit": 560.00, "credit": None, "balance": 124440.00, "category": "Food & Dining"},
    {"date": "08/04/2024", "val_date": "08/04/2024", "desc": "FLIPKART INTERNET PVT LTD BANGALORE\nELECTRONICS PURCHASE REF FK991827", "ref": "FK991827", "debit": 8999.00, "credit": None, "balance": 115441.00, "category": "Shopping"},
    {"date": "12/04/2024", "val_date": "12/04/2024", "desc": "TATA AIA LIFE INSURANCE ANNUAL PREMIUM\nPOLICY NO 0192837162 AUTO DEBIT", "ref": "TATA01928", "debit": 18500.00, "credit": None, "balance": 96941.00, "category": "Insurance"},
    {"date": "15/04/2024", "val_date": "15/04/2024", "desc": "PAYTM WALLET TOPUP VIA DEBIT CARD\nTXN ID 882910291827", "ref": "PAYTM882", "debit": 2000.00, "credit": None, "balance": 94941.00, "category": "Wallet Top-up"},
]

SAMPLE_4_TXNS_P2 = [
    {"date": "18/04/2024", "val_date": "18/04/2024", "desc": "INDIAN OIL PETROL PUMP WHITEFIELD\nVEHICLE FUEL REFILL", "ref": "IOCL9918", "debit": 2500.00, "credit": None, "balance": 92441.00, "category": "Fuel"},
    {"date": "22/04/2024", "val_date": "22/04/2024", "desc": "UPI/411294857162/Zomato/zomato@hdfcbank\nDINNER ORDER WITH FRIENDS", "ref": "411294857162", "debit": 1420.00, "credit": None, "balance": 91021.00, "category": "Food & Dining"},
    {"date": "25/04/2024", "val_date": "25/04/2024", "desc": "SALARY CREDIT TECH VENTURES INDIA LTD\nFOR THE MONTH OF APR 2024", "ref": "SAL202404", "debit": None, "credit": 110000.00, "balance": 201021.00, "category": "Salary/Income"},
    {"date": "28/04/2024", "val_date": "28/04/2024", "desc": "IRCTC TRAIN TICKET BOOKING BANGALORE TO CHENNAI\nPNR 4928172648", "ref": "IRCTC4928", "debit": 1840.00, "credit": None, "balance": 199181.00, "category": "Travel & Transport"},
    {"date": "30/04/2024", "val_date": "30/04/2024", "desc": "PRIME MINISTERS NATIONAL RELIEF FUND\nDONATION SECTION 80G", "ref": "PMNRF991", "debit": 5000.00, "credit": None, "balance": 194181.00, "category": "Donations/Charity"},
]


def generate_sample_1():
    """HDFC style: Separate Debit and Credit columns."""
    pdf_path = os.path.join(SAMPLES_DIR, "sample_1_hdfc.pdf")
    doc = SimpleDocTemplate(pdf_path, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()

    elements = []
    # Header
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=16, leading=20, textColor=colors.HexColor('#004c8f'))
    elements.append(Paragraph("<b>HDFC BANK LIMITED</b>", title_style))
    elements.append(Paragraph("Account Statement - Savings Account", styles['Normal']))
    elements.append(Spacer(1, 12))

    # Account metadata
    acc_data = [
        [Paragraph("<b>Customer Name:</b> ARJUN MEHTA", styles['Normal']), Paragraph("<b>Account No:</b> 50100293847561", styles['Normal'])],
        [Paragraph("<b>Customer ID:</b> 98271625", styles['Normal']), Paragraph("<b>IFSC Code:</b> HDFC0000240", styles['Normal'])],
        [Paragraph("<b>Branch:</b> KORAMANGALA 4TH BLOCK, BANGALORE", styles['Normal']), Paragraph("<b>MICR Code:</b> 560240003", styles['Normal'])],
        [Paragraph("<b>Statement Period:</b> 01/01/2024 to 31/01/2024", styles['Normal']), Paragraph("<b>Currency:</b> INR", styles['Normal'])],
        [Paragraph("<b>Opening Balance:</b> 1,00,000.00", styles['Normal']), Paragraph("<b>Closing Balance:</b> 1,82,210.50", styles['Normal'])],
    ]
    t_acc = Table(acc_data, colWidths=[270, 270])
    t_acc.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f5f7fa')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(t_acc)
    elements.append(Spacer(1, 16))

    # Table
    headers = ["Date", "Narration", "Chq/Ref No", "Value Dt", "Withdrawal (Dr)", "Deposit (Cr)", "Closing Balance"]
    table_data = [headers]
    for txn in SAMPLE_1_TXNS:
        dr = f"{txn['debit']:,.2f}" if txn['debit'] else ""
        cr = f"{txn['credit']:,.2f}" if txn['credit'] else ""
        bal = f"{txn['balance']:,.2f}"
        table_data.append([
            txn['date'],
            Paragraph(txn['desc'], styles['Normal']),
            txn['ref'],
            txn['val_date'],
            dr,
            cr,
            bal
        ])

    col_widths = [65, 180, 75, 65, 75, 75, 80]
    t_txns = Table(table_data, colWidths=col_widths, repeatRows=1)
    t_txns.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#004c8f')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (3, -1), 'LEFT'),
        ('ALIGN', (4, 0), (-1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(t_txns)
    doc.build(elements)

    # Save Ground Truth
    gt = {
        "bank_name": "HDFC BANK LIMITED",
        "account_holder_name": "ARJUN MEHTA",
        "account_number": "50100293847561",
        "customer_id": "98271625",
        "ifsc_code": "HDFC0000240",
        "micr_code": "560240003",
        "branch_name": "KORAMANGALA 4TH BLOCK, BANGALORE",
        "statement_period": "01/01/2024 to 31/01/2024",
        "opening_balance": 100000.00,
        "closing_balance": 182210.50,
        "currency": "INR",
        "transactions": [
            {
                "date": "2024-01-02",
                "description": txn['desc'],
                "debit": txn['debit'],
                "credit": txn['credit'],
                "balance": txn['balance'],
                "category": txn['category']
            } for txn in SAMPLE_1_TXNS
        ]
    }
    with open(os.path.join(SAMPLES_DIR, "sample_1_hdfc.json"), "w") as f:
        json.dump(gt, f, indent=2)


def generate_sample_2():
    """ICICI style: Single Amount + Dr/Cr indicator column."""
    pdf_path = os.path.join(SAMPLES_DIR, "sample_2_icici.pdf")
    doc = SimpleDocTemplate(pdf_path, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()

    elements = []
    # Header
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=16, leading=20, textColor=colors.HexColor('#b02a30'))
    elements.append(Paragraph("<b>ICICI BANK LIMITED</b>", title_style))
    elements.append(Paragraph("Statement of Transactions - Savings Account", styles['Normal']))
    elements.append(Spacer(1, 12))

    # Account metadata
    acc_data = [
        [Paragraph("<b>Account Name:</b> PRIYA SHARMA", styles['Normal']), Paragraph("<b>Account Number:</b> 000401582910", styles['Normal'])],
        [Paragraph("<b>Customer ID:</b> 54219876", styles['Normal']), Paragraph("<b>IFSC:</b> ICIC0000004", styles['Normal'])],
        [Paragraph("<b>Branch Name:</b> CONNAUGHT PLACE, NEW DELHI", styles['Normal']), Paragraph("<b>MICR:</b> 110229002", styles['Normal'])],
        [Paragraph("<b>Statement Period:</b> 01-02-2024 to 29-02-2024", styles['Normal']), Paragraph("<b>Currency:</b> INR", styles['Normal'])],
        [Paragraph("<b>Opening Balance:</b> 55,000.00", styles['Normal']), Paragraph("<b>Closing Balance:</b> 1,29,282.00", styles['Normal'])],
    ]
    t_acc = Table(acc_data, colWidths=[270, 270])
    t_acc.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fff5f5')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#fca5a5')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#fee2e2')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(t_acc)
    elements.append(Spacer(1, 16))

    # Table: Single Amount with Cr/Dr column
    headers = ["Tran Date", "Value Date", "Cheque No.", "Transaction Remarks", "Amount (INR)", "Cr/Dr", "Balance (INR)"]
    table_data = [headers]
    for txn in SAMPLE_2_TXNS:
        table_data.append([
            txn['date'],
            txn['val_date'],
            txn['ref'],
            Paragraph(txn['desc'], styles['Normal']),
            f"{txn['amount']:,.2f}",
            txn['type'],
            f"{txn['balance']:,.2f}"
        ])

    col_widths = [65, 65, 80, 195, 75, 45, 90]
    t_txns = Table(table_data, colWidths=col_widths, repeatRows=1)
    t_txns.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#b02a30')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (2, -1), 'LEFT'),
        ('ALIGN', (4, 0), (-1, -1), 'RIGHT'),
        ('ALIGN', (5, 0), (5, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(t_txns)
    doc.build(elements)

    # Save Ground Truth
    gt = {
        "bank_name": "ICICI BANK LIMITED",
        "account_holder_name": "PRIYA SHARMA",
        "account_number": "000401582910",
        "customer_id": "54219876",
        "ifsc_code": "ICIC0000004",
        "micr_code": "110229002",
        "branch_name": "CONNAUGHT PLACE, NEW DELHI",
        "statement_period": "01-02-2024 to 29-02-2024",
        "opening_balance": 55000.00,
        "closing_balance": 129282.00,
        "currency": "INR",
        "transactions": [
            {
                "date": "2024-02-" + txn['date'].split('-')[0],
                "description": txn['desc'],
                "debit": txn['amount'] if txn['type'] == "DR" else None,
                "credit": txn['amount'] if txn['type'] == "CR" else None,
                "balance": txn['balance'],
                "category": txn['category']
            } for txn in SAMPLE_2_TXNS
        ]
    }
    with open(os.path.join(SAMPLES_DIR, "sample_2_icici.json"), "w") as f:
        json.dump(gt, f, indent=2)


def generate_sample_3():
    """Kotak/Fintech style: Single signed amount column."""
    pdf_path = os.path.join(SAMPLES_DIR, "sample_3_kotak.pdf")
    doc = SimpleDocTemplate(pdf_path, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()

    elements = []
    # Header
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=16, leading=20, textColor=colors.HexColor('#da251c'))
    elements.append(Paragraph("<b>KOTAK MAHINDRA BANK</b>", title_style))
    elements.append(Paragraph("Consolidated Statement of Account", styles['Normal']))
    elements.append(Spacer(1, 12))

    # Account metadata
    acc_data = [
        [Paragraph("<b>Primary Account Holder:</b> VIKRAM RAO", styles['Normal']), Paragraph("<b>CRN / Account No:</b> 9182736450", styles['Normal'])],
        [Paragraph("<b>IFSC:</b> KKBK0000958", styles['Normal']), Paragraph("<b>Branch:</b> BANDRA WEST, MUMBAI", styles['Normal'])],
        [Paragraph("<b>Period:</b> 01/03/2024 - 31/03/2024", styles['Normal']), Paragraph("<b>Currency:</b> INR", styles['Normal'])],
        [Paragraph("<b>Opening Balance:</b> 90,000.00", styles['Normal']), Paragraph("<b>Closing Balance:</b> 1,08,547.00", styles['Normal'])],
    ]
    t_acc = Table(acc_data, colWidths=[270, 270])
    t_acc.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(t_acc)
    elements.append(Spacer(1, 16))

    # Table: Single signed Amount column
    headers = ["Date", "Description", "Reference ID", "Amount (INR)", "Balance (INR)"]
    table_data = [headers]
    for txn in SAMPLE_3_TXNS:
        amt_str = f"+{txn['amount']:,.2f}" if txn['amount'] > 0 else f"{txn['amount']:,.2f}"
        table_data.append([
            txn['date'],
            Paragraph(txn['desc'], styles['Normal']),
            txn['ref'],
            amt_str,
            f"{txn['balance']:,.2f}"
        ])

    col_widths = [80, 240, 95, 100, 100]
    t_txns = Table(table_data, colWidths=col_widths, repeatRows=1)
    t_txns.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#da251c')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (2, -1), 'LEFT'),
        ('ALIGN', (3, 0), (-1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(t_txns)
    doc.build(elements)

    # Save Ground Truth
    gt = {
        "bank_name": "KOTAK MAHINDRA BANK",
        "account_holder_name": "VIKRAM RAO",
        "account_number": "9182736450",
        "ifsc_code": "KKBK0000958",
        "branch_name": "BANDRA WEST, MUMBAI",
        "statement_period": "01/03/2024 - 31/03/2024",
        "opening_balance": 90000.00,
        "closing_balance": 108547.00,
        "currency": "INR",
        "transactions": [
            {
                "date": txn['date'],
                "description": txn['desc'],
                "debit": abs(txn['amount']) if txn['amount'] < 0 else None,
                "credit": txn['amount'] if txn['amount'] > 0 else None,
                "balance": txn['balance'],
                "category": txn['category']
            } for txn in SAMPLE_3_TXNS
        ]
    }
    with open(os.path.join(SAMPLES_DIR, "sample_3_kotak.json"), "w") as f:
        json.dump(gt, f, indent=2)


def generate_sample_4():
    """SBI style: Multi-page statement with multi-line descriptions and header continuation."""
    pdf_path = os.path.join(SAMPLES_DIR, "sample_4_sbi_multipage.pdf")
    doc = SimpleDocTemplate(pdf_path, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()

    elements = []
    # Header
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=16, leading=20, textColor=colors.HexColor('#224488'))
    elements.append(Paragraph("<b>STATE BANK OF INDIA</b>", title_style))
    elements.append(Paragraph("Account Statement - Personal Banking Branch", styles['Normal']))
    elements.append(Spacer(1, 12))

    # Account metadata
    acc_data = [
        [Paragraph("<b>Account Holder:</b> ANANYA IYER", styles['Normal']), Paragraph("<b>Account Number:</b> 30891245678", styles['Normal'])],
        [Paragraph("<b>CIF No:</b> 881928374", styles['Normal']), Paragraph("<b>IFS Code:</b> SBIN0001234", styles['Normal'])],
        [Paragraph("<b>Branch:</b> INDIRANAGAR BANGALORE", styles['Normal']), Paragraph("<b>MICR Code:</b> 560002015", styles['Normal'])],
        [Paragraph("<b>Statement Period:</b> 01/04/2024 to 30/04/2024", styles['Normal']), Paragraph("<b>Currency:</b> INR", styles['Normal'])],
        [Paragraph("<b>Opening Balance:</b> 1,50,000.00", styles['Normal']), Paragraph("<b>Closing Balance:</b> 1,94,181.00", styles['Normal'])],
    ]
    t_acc = Table(acc_data, colWidths=[270, 270])
    t_acc.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f0f4f8')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#94a3b8')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(t_acc)
    elements.append(Spacer(1, 16))

    headers = ["Txn Date", "Value Date", "Description", "Ref No.", "Debit", "Credit", "Balance"]

    # Page 1 table
    table_data_p1 = [headers]
    for txn in SAMPLE_4_TXNS_P1:
        dr = f"{txn['debit']:,.2f}" if txn['debit'] else ""
        cr = f"{txn['credit']:,.2f}" if txn['credit'] else ""
        table_data_p1.append([
            txn['date'],
            txn['val_date'],
            Paragraph(txn['desc'].replace('\n', '<br/>'), styles['Normal']),
            txn['ref'],
            dr,
            cr,
            f"{txn['balance']:,.2f}"
        ])

    col_widths = [60, 60, 160, 75, 60, 60, 65]
    t_p1 = Table(table_data_p1, colWidths=col_widths)
    t_p1.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#224488')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (3, -1), 'LEFT'),
        ('ALIGN', (4, 0), (-1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#94a3b8')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(t_p1)

    # Force PageBreak
    elements.append(PageBreak())

    # Page 2 header note
    elements.append(Paragraph("<b>STATE BANK OF INDIA - Statement Continuation (Page 2)</b>", styles['Normal']))
    elements.append(Spacer(1, 10))

    # Page 2 table (with repeated headers)
    table_data_p2 = [headers]
    for txn in SAMPLE_4_TXNS_P2:
        dr = f"{txn['debit']:,.2f}" if txn['debit'] else ""
        cr = f"{txn['credit']:,.2f}" if txn['credit'] else ""
        table_data_p2.append([
            txn['date'],
            txn['val_date'],
            Paragraph(txn['desc'].replace('\n', '<br/>'), styles['Normal']),
            txn['ref'],
            dr,
            cr,
            f"{txn['balance']:,.2f}"
        ])

    t_p2 = Table(table_data_p2, colWidths=col_widths)
    t_p2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#224488')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (3, -1), 'LEFT'),
        ('ALIGN', (4, 0), (-1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#94a3b8')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(t_p2)
    doc.build(elements)

    # Save Ground Truth
    all_txns = SAMPLE_4_TXNS_P1 + SAMPLE_4_TXNS_P2
    gt = {
        "bank_name": "STATE BANK OF INDIA",
        "account_holder_name": "ANANYA IYER",
        "account_number": "30891245678",
        "customer_id": "881928374",
        "ifsc_code": "SBIN0001234",
        "micr_code": "560002015",
        "branch_name": "INDIRANAGAR BANGALORE",
        "statement_period": "01/04/2024 to 30/04/2024",
        "opening_balance": 150000.00,
        "closing_balance": 194181.00,
        "currency": "INR",
        "transactions": [
            {
                "date": "2024-04-" + txn['date'].split('/')[0],
                "description": txn['desc'].replace('\n', ' '),
                "debit": txn['debit'],
                "credit": txn['credit'],
                "balance": txn['balance'],
                "category": txn['category']
            } for txn in all_txns
        ]
    }
    with open(os.path.join(SAMPLES_DIR, "sample_4_sbi_multipage.json"), "w") as f:
        json.dump(gt, f, indent=2)


def generate_scanned_pdf(source_pdf: str, output_pdf: str, rotate_deg: float = 0.5):
    """
    Rasterize source PDF into images and recreate as an image-only scanned PDF
    with slight rotation and simulated scan noise.
    """
    doc = pymupdf.open(source_pdf)
    new_doc = pymupdf.open()

    for page_idx in range(len(doc)):
        page = doc[page_idx]
        pix = page.get_pixmap(dpi=200)
        img_np = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
        if pix.n == 4:
            img_np = cv2.cvtColor(img_np, cv2.COLOR_RGBA2BGR)

        # Apply slight deskew/rotation
        h, w = img_np.shape[:2]
        center = (w // 2, h // 2)
        rot_mat = cv2.getRotationMatrix2D(center, rotate_deg, 1.0)
        rotated = cv2.warpAffine(img_np, rot_mat, (w, h), borderValue=(255, 255, 255))

        # Add subtle scanner noise
        noise = np.random.normal(0, 3, rotated.shape).astype(np.float32)
        noisy = np.clip(rotated.astype(np.float32) + noise, 0, 255).astype(np.uint8)

        # Encode back to PNG
        is_success, buffer = cv2.imencode(".png", noisy)
        img_bytes = buffer.tobytes()

        # Insert as new image page
        img_rect = pymupdf.Rect(0, 0, page.rect.width, page.rect.height)
        new_page = new_doc.new_page(width=page.rect.width, height=page.rect.height)
        new_page.insert_image(img_rect, stream=img_bytes)

    new_doc.save(output_pdf)
    new_doc.close()
    doc.close()


def generate_all_samples():
    print("Generating Sample 1 (HDFC - Debit/Credit columns)...")
    generate_sample_1()

    print("Generating Sample 2 (ICICI - Amount + Cr/Dr)...")
    generate_sample_2()

    print("Generating Sample 3 (Kotak - Signed Amount)...")
    generate_sample_3()

    print("Generating Sample 4 (SBI - Multi-page & Multi-line)...")
    generate_sample_4()

    print("Generating Scanned Image Sample 1 (Rasterized HDFC)...")
    generate_scanned_pdf(
        os.path.join(SAMPLES_DIR, "sample_1_hdfc.pdf"),
        os.path.join(SAMPLES_DIR, "sample_1_hdfc_scanned.pdf"),
        rotate_deg=0.3
    )

    print("Generating Scanned Image Sample 2 (Rasterized ICICI)...")
    generate_scanned_pdf(
        os.path.join(SAMPLES_DIR, "sample_2_icici.pdf"),
        os.path.join(SAMPLES_DIR, "sample_2_icici_scanned.pdf"),
        rotate_deg=-0.4
    )
    print("All samples generated successfully!")


if __name__ == "__main__":
    generate_all_samples()
