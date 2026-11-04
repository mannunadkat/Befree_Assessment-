"""Background job processing engine with Server-Sent Events (SSE) streaming."""

import os
import uuid
import asyncio
from typing import Dict, Any, Optional, List
from collections import defaultdict
from core.models import (
    JobStatus, JobFileStatus, ProcessingSettings, ProcessingResult,
    AccountDetails, Transaction, ValidationReport
)
from core.pdf_detector import detect_pdf_type
from core.text_extractor import extract_full_text
from core.layout_parser import extract_transactions_from_page
from core.account_parser import extract_account_details
from core.validator import reconcile_and_repair_transactions
from core.classifier.hybrid import classify_transaction
from core.recurring import detect_recurring_transactions
from core.csv_extractor import parse_csv_transactions
from core.json_extractor import parse_json_transactions


JOBS_STORE: Dict[str, Dict[str, Any]] = {}


def create_job(files: List[Dict[str, Any]], settings: ProcessingSettings) -> str:
    """Create a new job in queued status."""
    job_id = str(uuid.uuid4())
    file_statuses = [
        JobFileStatus(
            filename=f["name"],
            size_bytes=f["size"],
            status="queued"
        ) for f in files
    ]
    job_status = JobStatus(
        job_id=job_id,
        status="queued",
        stage="initializing",
        progress=0.0,
        files=file_statuses
    )

    JOBS_STORE[job_id] = {
        "status": job_status,
        "settings": settings,
        "files_data": files,  # [{"name": ..., "path": ..., "size": ...}]
        "event_queues": [],
        "result": None
    }
    return job_id


def get_file_password(f_name: str, passwords: Dict[str, str]) -> str:
    """Robust password lookup matching by filename, basename, substring, or single default credential."""
    if not passwords:
        return ""
    if f_name in passwords:
        return passwords[f_name]
    base = os.path.basename(f_name)
    if base in passwords:
        return passwords[base]
    # Check if any key is substring or vice versa
    for k, v in passwords.items():
        if k and (k in f_name or f_name in k or k.lower() in f_name.lower()):
            return v
    # If a single password was supplied, apply it to all encrypted files
    if len(passwords) == 1:
        return list(passwords.values())[0]
    if "default" in passwords:
        return passwords["default"]
    if "Statement" in passwords:
        return passwords["Statement"]
    return ""


async def emit_job_event(job_id: str, event_data: Dict[str, Any]):
    """Push SSE event to all connected listeners."""
    job = JOBS_STORE.get(job_id)
    if not job:
        return

    # Update in-memory job status
    if "status" in event_data:
        job["status"].status = event_data["status"]
    if "stage" in event_data:
        job["status"].stage = event_data["stage"]
    if "progress" in event_data:
        job["status"].progress = round(float(event_data["progress"]), 1)
    if "transactions_found" in event_data:
        job["status"].transactions_found = event_data["transactions_found"]
    if "file" in event_data:
        job["status"].current_file = event_data["file"]
    if "current_file" in event_data:
        job["status"].current_file = event_data["current_file"]
    if "message" in event_data and event_data.get("status") in ["error", "password_required"]:
        job["status"].error_message = event_data["message"]

    # Send to queues
    for q in list(job["event_queues"]):
        try:
            await q.put(event_data)
        except Exception:
            pass


def compute_analytics(transactions: List[Transaction], account: Optional[AccountDetails] = None) -> Dict[str, Any]:
    """Compute aggregates, charts data, and automated insights."""
    if account and account.total_debits_reported is not None and account.total_credits_reported is not None:
        total_debits = account.total_debits_reported
        total_credits = account.total_credits_reported
    else:
        total_debits = sum((t.debit or 0.0) for t in transactions)
        total_credits = sum((t.credit or 0.0) for t in transactions)
    net_flow = total_credits - total_debits

    # Category totals
    cat_spend = defaultdict(float)
    cat_income = defaultdict(float)
    cat_counts = defaultdict(int)
    merchant_spend = defaultdict(float)
    monthly_data = defaultdict(lambda: {"income": 0.0, "expense": 0.0})

    for t in transactions:
        m = t.date[:7] if len(t.date) >= 7 else "Unknown"
        if t.debit:
            cat_spend[t.category] += t.debit
            monthly_data[m]["expense"] += t.debit
            m_name = t.counterparty or "Other"
            merchant_spend[m_name] += t.debit
        if t.credit:
            cat_income[t.category] += t.credit
            monthly_data[m]["income"] += t.credit
        cat_counts[t.category] += 1

    # Top expenses
    top_expenses = sorted(
        [t for t in transactions if t.debit and t.debit > 0],
        key=lambda x: x.debit or 0.0,
        reverse=True
    )[:10]

    # Top merchants
    top_merchants = sorted(
        [{"merchant": k, "amount": round(v, 2)} for k, v in merchant_spend.items() if k != "Other"],
        key=lambda x: x["amount"],
        reverse=True
    )[:8]

    # Automated insights
    biggest_cat = max(cat_spend.items(), key=lambda x: x[1])[0] if cat_spend else "None"
    biggest_cat_amt = cat_spend.get(biggest_cat, 0.0)
    highest_single = top_expenses[0].debit if top_expenses else 0.0
    highest_single_desc = top_expenses[0].description if top_expenses else "None"

    # Distinct days
    distinct_days = len(set(t.date for t in transactions if t.date))
    avg_daily_spend = (total_debits / max(1, distinct_days)) if distinct_days else 0.0

    recurring_count = sum(1 for t in transactions if t.is_recurring)

    insights = [
        {
            "title": "Biggest Spending Category",
            "value": f"{biggest_cat}",
            "subtext": f"₹{biggest_cat_amt:,.2f} ({((biggest_cat_amt / total_debits)*100 if total_debits else 0):.1f}% of total spend)",
            "icon": "pie-chart"
        },
        {
            "title": "Average Daily Spend",
            "value": f"₹{avg_daily_spend:,.2f}",
            "subtext": f"Across {distinct_days} transaction days",
            "icon": "activity"
        },
        {
            "title": "Detected Subscriptions",
            "value": f"{recurring_count} transactions",
            "subtext": "Recurring monthly/periodic payments",
            "icon": "repeat"
        },
        {
            "title": "Highest Single Expense",
            "value": f"₹{highest_single:,.2f}",
            "subtext": highest_single_desc[:35] + ("..." if len(highest_single_desc) > 35 else ""),
            "icon": "alert-circle"
        }
    ]

    sorted_months = sorted(monthly_data.keys())
    return {
        "kpis": {
            "total_credits": round(total_credits, 2),
            "total_debits": round(total_debits, 2),
            "net_flow": round(net_flow, 2),
            "total_transactions": len(transactions),
        },
        "category_spending": {k: round(v, 2) for k, v in sorted(cat_spend.items(), key=lambda x: x[1], reverse=True)},
        "category_counts": dict(cat_counts),
        "monthly_summary": {
            "labels": sorted_months,
            "income": [round(monthly_data[m]["income"], 2) for m in sorted_months],
            "expense": [round(monthly_data[m]["expense"], 2) for m in sorted_months],
            "net": [round(monthly_data[m]["income"] - monthly_data[m]["expense"], 2) for m in sorted_months]
        },
        "top_merchants": top_merchants,
        "top_expenses": [
            {
                "date": t.date,
                "description": t.description,
                "amount": t.debit,
                "category": t.category
            } for t in top_expenses
        ],
        "insights": insights
    }


async def process_job_pipeline(job_id: str):
    """Full asynchronous background pipeline execution with real-time SSE progress."""
    job = JOBS_STORE.get(job_id)
    if not job:
        return

    settings: ProcessingSettings = job["settings"]
    files_data = job["files_data"]

    try:
        await emit_job_event(job_id, {
            "status": "processing",
            "stage": "detecting",
            "progress": 5.0,
            "message": "Detecting PDF page types and checking passwords..."
        })

        all_transactions: List[Transaction] = []
        combined_account: Optional[AccountDetails] = None
        total_pages_all_files = 0
        overall_doc_type = "text"

        # Step 1: Detect PDF/CSV types per file and page
        for f_idx, f_info in enumerate(files_data):
            f_path = f_info["path"]
            f_name = f_info["name"]
            f_status = job["status"].files[f_idx]
            f_status.status = "detecting"

            if f_name.lower().endswith(".csv"):
                f_status.detected_type = "csv"
                f_status.pages = 1
                f_status.page_types = {1: "text"}
                total_pages_all_files += 1
                continue

            if f_name.lower().endswith(".json"):
                f_status.detected_type = "json"
                f_status.pages = 1
                f_status.page_types = {1: "text"}
                total_pages_all_files += 1
                continue

            pwd = get_file_password(f_name, settings.passwords)
            det_res = detect_pdf_type(f_path, password=pwd)

            if det_res.get("password_required"):
                f_status.status = "password_required"
                f_status.error = det_res.get("error") or "Password required to decrypt this statement."
                job["status"].status = "password_required"
                job["status"].current_file = f_name
                job["status"].error_message = f"File '{f_name}': {f_status.error}"
                await emit_job_event(job_id, {
                    "status": "password_required",
                    "file": f_name,
                    "message": f"Password required for {f_name}"
                })
                return

            if det_res.get("doc_type") == "invalid" or det_res.get("doc_nature") == "invoice":
                err_msg = det_res.get("error") or "Invalid document format: Uploaded file is not a valid bank statement."
                f_status.status = "error"
                f_status.error = err_msg
                job["status"].status = "error"
                job["status"].error_message = err_msg
                await emit_job_event(job_id, {
                    "status": "error",
                    "file": f_name,
                    "message": err_msg
                })
                return

            if det_res.get("doc_type") == "empty":
                f_status.status = "done"
                f_status.detected_type = "empty"
                f_status.pages = det_res.get("page_count", 0)
                continue

            f_status.detected_type = det_res["doc_type"]
            f_status.pages = det_res["page_count"]
            f_status.page_types = det_res["pages"]
            total_pages_all_files += det_res["page_count"]
            if det_res["doc_type"] in ["scanned", "hybrid"]:
                overall_doc_type = det_res["doc_type"]

        job["status"].total_pages = total_pages_all_files
        pages_processed = 0

        # Step 2: Extraction per file
        for f_idx, f_info in enumerate(files_data):
            f_path = f_info["path"]
            f_name = f_info["name"]
            f_status = job["status"].files[f_idx]

            if f_name.lower().endswith(".csv"):
                f_status.status = "extracting"
                csv_txns, csv_acct = parse_csv_transactions(f_path, f_name)
                all_transactions.extend(csv_txns)
                if combined_account is None:
                    combined_account = csv_acct
                f_status.status = "done"
                pages_processed += 1
                continue

            if f_name.lower().endswith(".json"):
                f_status.status = "extracting"
                json_txns, json_acct = parse_json_transactions(f_path, f_name)
                all_transactions.extend(json_txns)
                if combined_account is None:
                    combined_account = json_acct
                f_status.status = "done"
                pages_processed += 1
                continue

            pwd = get_file_password(f_name, settings.passwords)

            # Account Header extraction
            f_status.status = "extracting"
            full_text = extract_full_text(f_path, password=pwd)

            # If document is scanned or text is empty, extract OCR text from page 1 and the last page
            if not full_text.strip() or f_status.detected_type in ["scanned", "hybrid"]:
                try:
                    from core.ocr_extractor import is_tesseract_available
                    if is_tesseract_available():
                        from core.ocr_extractor import extract_words_from_scanned_page
                        p1_words, _ = extract_words_from_scanned_page(f_path, 1, dpi=settings.ocr_dpi, password=pwd)
                        ocr_blobs = [" ".join(w["text"] for w in p1_words)]
                        if f_status.pages > 1:
                            pn_words, _ = extract_words_from_scanned_page(f_path, f_status.pages, dpi=settings.ocr_dpi, password=pwd)
                            ocr_blobs.append(" ".join(w["text"] for w in pn_words))
                        full_text = (full_text + "\n" + "\n".join(ocr_blobs)).strip()
                except Exception as e:
                    print(f"Warning: OCR header text extraction failed: {e}")

            account_info = extract_account_details(full_text)
            account_info.pdf_type = f_status.detected_type
            account_info.page_types = f_status.page_types

            if combined_account is None:
                combined_account = account_info

            # Page by page extraction
            saved_boundaries = None
            for p_num in range(1, f_status.pages + 1):
                pages_processed += 1
                is_scanned_page = (f_status.page_types.get(p_num) == "scanned")

                stage_name = "ocr" if is_scanned_page else "extracting"
                f_status.status = stage_name
                progress_pct = 10.0 + (pages_processed / max(1, total_pages_all_files)) * 50.0

                await emit_job_event(job_id, {
                    "stage": stage_name,
                    "progress": progress_pct,
                    "current_file": f_name,
                    "current_page": p_num,
                    "total_pages": total_pages_all_files,
                    "transactions_found": len(all_transactions),
                    "message": f"Processing page {p_num} of {f_status.pages} ({'OCR' if is_scanned_page else 'Text'})"
                })

                txns_page, bounds = extract_transactions_from_page(
                    pdf_path=f_path,
                    page_number=p_num,
                    is_scanned=is_scanned_page,
                    saved_boundaries=saved_boundaries,
                    dpi=settings.ocr_dpi,
                    password=pwd
                )
                if bounds:
                    saved_boundaries = bounds

                for tx in txns_page:
                    tx.source_file = f_name
                    tx.page = p_num

                all_transactions.extend(txns_page)
                # Small yield for smooth SSE streaming
                await asyncio.sleep(0.02)

            f_status.status = "done"

        # Step 3: Deduplication (if enabled)
        if settings.dedupe and len(all_transactions) > 1:
            seen_signatures = set()
            deduped_txns = []
            for t in all_transactions:
                amt = t.debit if t.debit is not None else t.credit
                sig = (t.date, t.description.strip().lower()[:20], amt, t.balance)
                if sig not in seen_signatures:
                    seen_signatures.add(sig)
                    deduped_txns.append(t)
            all_transactions = deduped_txns

        # Step 4: Balance Validation and Auto-repair
        await emit_job_event(job_id, {
            "stage": "validating",
            "progress": 70.0,
            "transactions_found": len(all_transactions),
            "message": "Reconciling running balance and executing auto-repair..."
        })
        await asyncio.sleep(0.05)

        validated_txns, validation_report = reconcile_and_repair_transactions(
            all_transactions,
            opening_balance=combined_account.opening_balance if combined_account else None,
            closing_balance=combined_account.closing_balance if combined_account else None,
            total_debits_reported=combined_account.total_debits_reported if combined_account else None,
            total_credits_reported=combined_account.total_credits_reported if combined_account else None
        )

        # Step 5: Classification Engine (Rules + ML)
        await emit_job_event(job_id, {
            "stage": "classifying",
            "progress": 85.0,
            "transactions_found": len(validated_txns),
            "message": "Classifying transactions with heuristic rules & ML model..."
        })
        await asyncio.sleep(0.05)

        for t in validated_txns:
            classify_transaction(t, confidence_threshold=settings.confidence_threshold)

        # Detect Recurring Transactions
        detect_recurring_transactions(validated_txns)

        # Step 6: Compute Analytics Aggregates
        analytics = compute_analytics(validated_txns, combined_account)

        if combined_account:
            combined_account.pdf_type = overall_doc_type

        # Build final ProcessingResult
        result = ProcessingResult(
            account=combined_account or AccountDetails(),
            transactions=validated_txns,
            validation=validation_report,
            analytics=analytics
        )
        job["result"] = result

        completion_msg = f"Successfully processed {len(validated_txns)} transactions!"
        from core.ocr_extractor import is_tesseract_available
        if not is_tesseract_available() and overall_doc_type in ["scanned", "hybrid"]:
            completion_msg = f"Processed {len(validated_txns)} transactions from text pages (Note: Scanned pages require local Tesseract OCR engine)."

        await emit_job_event(job_id, {
            "status": "completed",
            "stage": "completed",
            "progress": 100.0,
            "transactions_found": len(validated_txns),
            "message": completion_msg
        })

    except Exception as e:
        import traceback
        err_msg = str(e)
        job["status"].status = "error"
        job["status"].error_message = err_msg
        await emit_job_event(job_id, {
            "status": "error",
            "stage": "error",
            "progress": 100.0,
            "message": f"Error: {err_msg}"
        })
        print(f"Error processing job {job_id}: {err_msg}\n{traceback.format_exc()}")
