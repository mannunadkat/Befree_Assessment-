"""Generate rich seed training dataset for classical ML classifier."""

import os
import csv
import random

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "training_data.csv")

TEMPLATES = {
    "Salary/Income": [
        "SALARY CREDIT FOR {mon} {year} {comp} PVT LTD",
        "CMS/SALARY/{comp}/EMP{id}/{mon}",
        "NEFT CR-{ifsc}-{comp} CORP-SALARY",
        "PAYROLL DIRECT DEPOSIT {comp} TECHNOLOGIES",
        "MONTHLY WAGES FOR {mon} {year}",
        "CONSULTING FEES INVOICE INV-{id}",
        "CLIENT PAYMENT FOR SOFTWARE SERVICES {comp}",
        "STIPEND PAYMENT {comp} INTERNSHIP",
        "BONUS DISBURSEMENT ANNUAL PERFORMANCE {comp}"
    ],
    "Transfer In": [
        "NEFT CR-{ifsc}-{name}-FUNDS TRANSFER",
        "IMPS-P2A-{ref}-{name}-GIFT",
        "UPI/{ref}/{name}/{handle}@okaxis",
        "FT FROM {name} SAVINGS AC",
        "RECEIVED FROM {name} VIA GOOGLE PAY",
        "TRANSFER IN FROM {name} SPLIT EXPENSES"
    ],
    "Transfer Out (Person)": [
        "UPI/{ref}/{name}/{handle}@oksbi",
        "NEFT DR-{ifsc}-{name}-LENT MONEY",
        "IMPS OUT {ref} TO {name}",
        "FT TO {name} LOAN RETURN",
        "PAID TO {name} DINNER SHARE",
        "SENT MONEY TO {name} VIA PHONEPE"
    ],
    "Food & Dining": [
        "UPI/{ref}/Swiggy/swiggy@axis ORDER {id}",
        "UPI/{ref}/Zomato/zomato@hdfc DINNER DELIVERY",
        "POS DEBIT DOMINOS PIZZA OUTLET {id}",
        "MCDONALDS RESTAURANT FOOD BLR {id}",
        "STARBUCKS COFFEE KORAMANGALA {id}",
        "BURGER KING INDIRANAGAR FOOD {id}",
        "CAFE COFFEE DAY AIRPORT RD {id}",
        "SUBWAY SANDWICHES MALL COUNTER {id}",
        "HALDIRAMS FOODS SWEETS RESTAURANT {id}"
    ],
    "Groceries": [
        "UPI/{ref}/Blinkit/blinkit@icici GROCERY",
        "UPI/{ref}/Zepto/zepto@axis QUICK COMMERCE",
        "POS/BIGBASKET INDIRANAGAR/{id}",
        "BBDAY GROCERIES SUBSCRIPTION {id}",
        "DMART SUPERMARKET PROVISIONS {id}",
        "RELIANCE FRESH VEGETABLES STORE {id}",
        "SPENCERS RETAIL GROCERY STORE {id}",
        "NATURES BASKET ORGANIC FOODS {id}"
    ],
    "Shopping": [
        "Amazon.in Payments retail order {id}",
        "FLIPKART INTERNET PVT LTD BANGALORE {id}",
        "MYNTRA DESIGNS PVT LTD CLOTHING {id}",
        "AJIO ONLINE FASHION STORE {id}",
        "ZARA RETAIL CLOTHING STORE {id}",
        "H&M APPAREL STORE PHOENIX MALL {id}",
        "DECATHLON SPORTS INDIA GEAR {id}",
        "CROMA ELECTRONICS APPLIANCES {id}",
        "NYKAA E-RETAIL COSMETICS ORDER {id}"
    ],
    "Travel & Transport": [
        "UPI/{ref}/Uber India/uber@axis RIDE {id}",
        "UPI/{ref}/Ola Cabs/olacabs@icici CITY RIDE",
        "RAPIDO BIKE TAXI COMMUTE {id}",
        "IRCTC TRAIN TICKET BOOKING PNR {id}",
        "INDIAN RAILWAY PASSENGER TICKET {id}",
        "MAKEMYTRIP INDIA PVT LTD FLIGHT {id}",
        "GOINDIGO AIRLINES TICKET BOOKING {id}",
        "FASTAG TOLL RECHARGE NHAI TOLL {id}",
        "METRO SMART CARD RECHARGE BMRCL {id}"
    ],
    "Fuel": [
        "UPI/{ref}/HPCL FUEL PUMP BLR",
        "BHARAT PETROLEUM PETROL BUNK {id}",
        "INDIAN OIL CORP PETROL REFILL {id}",
        "SHELL AUTO FUEL STATION DIESEL {id}",
        "IOCL PETROL DIESEL WHITEFIELD {id}",
        "HPCL RETAIL OUTLET FUEL BLR {id}"
    ],
    "Utilities & Bills": [
        "ELECTRICITY BILL BESCOM BANGALORE {id}",
        "TNEB POWER BILL ONLINE PAYMENT {id}",
        "MAHARASHTRA STATE ELECTRICITY MSEB {id}",
        "PIPED NATURAL GAS IGL NEW DELHI {id}",
        "BWSSB WATER SUPPLY BILL BLR {id}",
        "MAHANAGAR GAS LTD PNG UTILITY {id}"
    ],
    "Mobile/Internet/DTH Recharge": [
        "JIO PREPAID RECHARGE {num} {id}",
        "AIRTEL MOBILE BILL POSTPAID {id}",
        "VODAFONE IDEA VI RECHARGE {num}",
        "ACT FIBERNET BROADBAND BILL {id}",
        "TATA PLAY DTH RECHARGE SUB {id}",
        "AIRTEL DTH DIGITAL TV RECHARGE {id}"
    ],
    "Rent": [
        "HOUSE RENT FOR {mon} {year} PAID TO LANDLORD",
        "FLAT RENT APARTMENT {id} {mon}",
        "RENT PAYMENT TO PROPERTY OWNER MR {name}",
        "MONTHLY HOUSE RENT VIA NEFT",
        "PG ACCOMMODATION RENT {mon}"
    ],
    "EMI/Loan": [
        "HDFC HOME LOAN EMI {id}",
        "BAJAJ FINSERV CONSUMER DURABLE EMI {id}",
        "ICICI AUTO LOAN MONTHLY EMI {id}",
        "SBI PERSONAL LOAN INSTALLMENT {id}",
        "HDB FINANCIAL SERVICES EMI {id}",
        "AXIS BANK TWO WHEELER LOAN EMI {id}"
    ],
    "Insurance": [
        "HDFC ERGO HEALTH INSURANCE PREMIUM",
        "TATA AIA LIFE INSURANCE ANNUAL POLICY {id}",
        "LIC OF INDIA LIFE POLICY PREMIUM {id}",
        "STAR HEALTH ALLIED INSURANCE {id}",
        "ICICI LOMBARD MOTOR VEHICLE INSURANCE {id}",
        "MAX LIFE INSURANCE POLICY {id}"
    ],
    "Investments/Mutual Funds/SIP": [
        "ACH/GROWW/SIP-MUTUAL-FUND-{id}",
        "HDFC MUTUAL FUND SYSTEMATIC INVESTMENT",
        "SBI MUTUAL FUND SIP ACH DEBIT {id}",
        "NIPPON INDIA GROWTH FUND SIP",
        "UTI MUTUAL FUND SIP AUTO DEBIT",
        "ICICI PRUDENTIAL MF EQUITY SIP {id}"
    ],
    "Stocks": [
        "ZERODHA BROKING LTD EQUITY FUNDS",
        "GROWW INVESTMENTS EQUITY TRADING {id}",
        "UPSTOX RKSV SECURITIES BROKING",
        "ANGEL ONE SHARE TRADING MARGIN {id}",
        "ICICI DIRECT SHARE TRADING ACCOUNT",
        "MOTILAL OSWAL SECURITIES TRADING"
    ],
    "Entertainment/Subscriptions": [
        "NETFLIX MUMBAI IN RET {id}",
        "SPOTIFY PREMIUM MUSIC SUBSCRIPTION",
        "DISNEY PLUS HOTSTAR ANNUAL SUB {id}",
        "YOUTUBE PREMIUM FAMILY MEMBERSHIP",
        "AMAZON PRIME VIDEO YEARLY {id}",
        "BOOKMYSHOW CINEMA TICKETS {id}",
        "PVR CINEMAS MOVIE TICKETS {id}"
    ],
    "Healthcare": [
        "APOLLO PHARMACY BANGALORE MEDICINES",
        "PHARMEASY ONLINE DRUGS PURCHASE {id}",
        "TATA 1MG HEALTHCARE MEDICINES",
        "MANIPAL HOSPITAL CONSULTATION BILL",
        "FORTIS HEALTHCARE LAB TESTS {id}",
        "DR LAL PATHLABS BLOOD DIAGNOSTICS {id}"
    ],
    "Education": [
        "DELHI PUBLIC SCHOOL TUITION FEES {id}",
        "UDEMY ONLINE COURSE PURCHASE {id}",
        "COURSERA INC SUBSCRIPTION EDUCATION",
        "COLLEGE SEMESTER TUITION FEE {id}",
        "UNACADEMY SUBSCRIPTION EXAM PREP",
        "BYJUS LEARNING PROGRAM COURSE {id}"
    ],
    "ATM Withdrawal": [
        "ATM WDL CASH HDFC ATM KORAMANGALA BLR",
        "SBI ATM CASH WITHDRAWAL INDIRANAGAR",
        "NFS CASH WDL DOMESTIC ATM {id}",
        "ICICI BANK ATM CASH WDL SOUTH EX",
        "ATM CASH WITHDRAWAL SELF DEBIT"
    ],
    "Cash Deposit": [
        "CASH DEPOSIT BY CASH BRANCH COUNTER",
        "CDM CASH DEPOSIT MACHINE {id}",
        "BY CASH SELF DEPOSITED AT BRANCH",
        "CASH RECVD AT TELLER COUNTER {id}"
    ],
    "Bank Charges/Fees": [
        "ANNUAL SMS CHARGES + GST {id}",
        "CONSOLIDATED CHARGES FOR DEBIT CARD AMC",
        "MINIMUM BALANCE PENALTY CHARGES",
        "CHEQUE BOUNCE CHARGES + GST",
        "ATM INTERCHANGE CHARGES NON HOME BANK",
        "FOLIO MAINTENANCE CHARGES Q4"
    ],
    "Interest Earned": [
        "QUARTERLY SAVINGS INTEREST CREDITED",
        "INT.PD SB ACCOUNT FOR THE QUARTER",
        "FIXED DEPOSIT INTEREST PAYOUT {id}",
        "SAVINGS BANK INTEREST CREDIT AUTO",
        "TERM DEPOSIT MONTHLY INTEREST CREDIT"
    ],
    "Tax (GST/TDS/Income Tax)": [
        "INCOME TAX ADVANCE TAX CHALLAN 280",
        "GST GOVERNMENT PAYMENT PMT-06 {id}",
        "TDS DEDUCTION UNDER SECTION 194J",
        "MUNICIPAL PROPERTY TAX PAYMENT {id}",
        "SELF ASSESSMENT TAX PAYMENT CHALLAN"
    ],
    "Refund/Reversal": [
        "REFUND/AMZN-MKTPLACE-IN/{id}",
        "REVERSAL OF FAILED UPI TXN {id}",
        "SWIGGY REFUND FOR CANCELLED ORDER",
        "FLIPKART RETURN REFUND CREDIT {id}",
        "ZOMATO ORDER CANCELLATION REFUND",
        "CHARGEBACK REVERSAL FOR WRONG DEBIT"
    ],
    "Cheque": [
        "CHEQUE CLEARING CTS CHQ NO {id}",
        "LOCAL CLEARING CHQ PAID OUTWARD",
        "INWARD CHEQUE CLEARING CHQ {id}",
        "CHEQUE DEPOSIT PROCEEDS CREDITED"
    ],
    "Credit Card Payment": [
        "CRED CLUB CREDIT CARD BILL PAYMENT",
        "HDFC BANK CREDIT CARD BILL AUTOPAY",
        "SBI CARD ONLINE BILL PAYMENT {id}",
        "ICICI BANK CREDIT CARD PAYMENT",
        "AMERICAN EXPRESS CARD PAYMENT {id}",
        "AXIS BANK CC BILL DESK PAYMENT"
    ],
    "Wallet Top-up": [
        "PAYTM WALLET TOPUP VIA DEBIT CARD",
        "AMAZON PAY WALLET BALANCE ADD {id}",
        "MOBIKWIK WALLET LOAD MONEY",
        "PHONEPE WALLET AUTO TOPUP {id}"
    ],
    "Donations/Charity": [
        "PRIME MINISTERS NATIONAL RELIEF FUND DONATION",
        "PM CARES FUND 80G CONTRIBUTION {id}",
        "AKSHAYA PATRA FOUNDATION CHARITY",
        "GIVEINDIA RELIEF DONATION NGO",
        "CHIEF MINISTERS RELIEF FUND DONATION"
    ]
}

NAMES = ["Rahul Sharma", "Priya Verma", "Amit Patel", "Sneha Rao", "Rohan Iyer", "Deepak Gupta", "Ananya Das", "Suresh Kumar"]
COMPS = ["TCS", "Infosys", "Wipro", "HCL", "Cognizant", "Google India", "Amazon Tech", "Accenture", "Microsoft India"]
MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
IFSCS = ["HDFC0000240", "SBIN0001234", "ICIC0000004", "UTIB0000123", "KKBK0000958"]


def generate_seed_dataset():
    records = []
    # Generate ~25-30 variations per category -> ~700+ rows
    for cat, templates in TEMPLATES.items():
        for _ in range(25):
            for t in templates:
                desc = t.format(
                    mon=random.choice(MONTHS),
                    year=random.choice(["2023", "2024"]),
                    comp=random.choice(COMPS),
                    name=random.choice(NAMES),
                    ifsc=random.choice(IFSCS),
                    handle=random.choice(["user", "pay", "acc", "quick"]),
                    id=str(random.randint(100000, 999999)),
                    ref=str(random.randint(400000000000, 499999999999)),
                    num=str(random.randint(9000000000, 9999999999))
                )
                # Randomize case / noise
                if random.random() < 0.2:
                    desc = desc.lower()
                records.append({"description": desc, "category": cat})

    # Shuffle
    random.shuffle(records)

    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["description", "category"])
        writer.writeheader()
        writer.writerows(records)

    print(f"Generated {len(records)} training samples in {OUTPUT_PATH}")


if __name__ == "__main__":
    generate_seed_dataset()
