"""Data models for Bank Statement Processing & Classification System."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import uuid


class AccountDetails(BaseModel):
    account_holder_name: Optional[str] = None
    account_number: Optional[str] = None
    masked_account_number: Optional[str] = None
    bank_name: Optional[str] = None
    ifsc_code: Optional[str] = None
    micr_code: Optional[str] = None
    branch_name: Optional[str] = None
    customer_id: Optional[str] = None
    statement_period: Optional[str] = None
    opening_balance: Optional[float] = None
    closing_balance: Optional[float] = None
    total_debits_reported: Optional[float] = None
    total_credits_reported: Optional[float] = None
    currency: str = "INR"
    pdf_type: str = "text"  # "text" | "scanned" | "hybrid"
    page_types: Dict[int, str] = Field(default_factory=dict)


class Transaction(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    date: str
    value_date: Optional[str] = None
    description: str
    ref_no: Optional[str] = None
    payment_mode: str = "Other"
    counterparty: Optional[str] = None
    debit: Optional[float] = None
    credit: Optional[float] = None
    balance: Optional[float] = None
    category: str = "Uncategorized"
    category_confidence: float = 0.0
    classification_source: str = "rule"  # "rule" | "ml" | "manual"
    is_recurring: bool = False
    validation_status: str = "OK"  # "OK" | "Repaired" | "Mismatch"
    validation_note: Optional[str] = None
    source_file: str = ""
    page: int = 1
    bbox: Optional[List[float]] = None  # [x0, top, x1, bottom]
    ocr_confidence: Optional[float] = None
    raw_amount: Optional[str] = None


class ValidationIssue(BaseModel):
    transaction_id: str
    row_index: int
    page: int
    issue_type: str  # "balance_mismatch" | "swapped_columns" | "digit_repair" | "unrepaired"
    expected_balance: float
    actual_balance: float
    description: str
    auto_repaired: bool = False
    repair_details: Optional[str] = None


class ValidationReport(BaseModel):
    total_rows: int = 0
    ok_rows: int = 0
    repaired_rows: int = 0
    mismatch_rows: int = 0
    opening_balance: Optional[float] = None
    closing_balance: Optional[float] = None
    calculated_closing_balance: Optional[float] = None
    total_debits: float = 0.0
    total_credits: float = 0.0
    is_reconciled: bool = False
    discrepancy: float = 0.0
    issues: List[ValidationIssue] = Field(default_factory=list)


class JobFileStatus(BaseModel):
    filename: str
    size_bytes: int = 0
    status: str = "queued"  # "queued", "detecting", "extracting", "ocr", "classifying", "done", "error"
    detected_type: str = "unknown"  # "text", "scanned", "hybrid"
    pages: int = 0
    page_types: Dict[int, str] = Field(default_factory=dict)
    error: Optional[str] = None


class JobStatus(BaseModel):
    job_id: str
    status: str = "queued"  # "queued", "processing", "completed", "error", "password_required"
    stage: str = "initializing"
    progress: float = 0.0
    current_file: Optional[str] = None
    current_page: int = 0
    total_pages: int = 0
    transactions_found: int = 0
    files: List[JobFileStatus] = Field(default_factory=list)
    error_message: Optional[str] = None


class ProcessingSettings(BaseModel):
    ocr_dpi: int = 200
    confidence_threshold: float = 0.55
    dedupe: bool = True
    merge_files: bool = True
    mask_account_number: bool = True
    passwords: Dict[str, str] = Field(default_factory=dict)  # filename -> password


class ProcessingResult(BaseModel):
    account: AccountDetails
    transactions: List[Transaction]
    validation: ValidationReport
    analytics: Dict[str, Any] = Field(default_factory=dict)
