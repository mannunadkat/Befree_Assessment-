"""API routes for file upload, SSE streaming, results, overrides, retrain, export, and preview."""

import os
import json
import asyncio
from typing import List, Optional
try:
    import cv2
except ImportError:
    cv2 = None
import numpy as np
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel
from core.models import ProcessingSettings
from api.jobs import (
    JOBS_STORE, create_job, process_job_pipeline, emit_job_event,
    compute_analytics, get_file_password
)
from core.classifier.hybrid import record_user_override
from core.classifier.train import train_model
from core.exporter import export_to_csv, export_to_excel
from core.text_extractor import render_page_to_bytes
import pymupdf


router = APIRouter(prefix="/api")

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "uploads")
SAMPLES_DIR = os.path.join(os.path.dirname(__file__), "..", "samples")
try:
    os.makedirs(UPLOAD_DIR, exist_ok=True)
except OSError:
    UPLOAD_DIR = "/tmp/uploads"
    os.makedirs(UPLOAD_DIR, exist_ok=True)


class OverrideRequest(BaseModel):
    job_id: str
    txn_id: str
    category: str


@router.post("/upload")
async def upload_files(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    settings: str = Form("{}")
):
    """Handle multiple PDF uploads and trigger background processing pipeline."""
    try:
        settings_dict = json.loads(settings)
    except Exception:
        settings_dict = {}

    proc_settings = ProcessingSettings(**settings_dict)

    saved_files = []
    for f in files:
        ext = os.path.splitext(f.filename.lower())[1]
        if ext not in [".pdf", ".csv", ".json"]:
            raise HTTPException(status_code=400, detail=f"File '{f.filename}' is not a supported format (.pdf, .csv, or .json).")

        file_id = f"{uuid_str()[:8]}_{f.filename}"
        dest_path = os.path.join(UPLOAD_DIR, file_id)

        contents = await f.read()
        with open(dest_path, "wb") as out:
            out.write(contents)

        saved_files.append({
            "name": f.filename,
            "path": dest_path,
            "size": len(contents)
        })

    job_id = create_job(saved_files, proc_settings)
    background_tasks.add_task(process_job_pipeline, job_id)

    return {"job_id": job_id, "status": "queued"}


def uuid_str() -> str:
    import uuid
    return str(uuid.uuid4())


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Retrieve current processing status for a job."""
    job = JOBS_STORE.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job["status"]


@router.get("/jobs/{job_id}/events")
async def stream_job_events(job_id: str):
    """Server-Sent Events (SSE) stream for real-time progress updates."""
    job = JOBS_STORE.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    queue = asyncio.Queue()
    job["event_queues"].append(queue)

    async def event_generator():
        try:
            # Yield initial status immediately
            init_data = json.dumps({
                "status": job["status"].status,
                "stage": job["status"].stage,
                "progress": job["status"].progress,
                "transactions_found": job["status"].transactions_found,
                "file": job["status"].current_file,
                "message": job["status"].error_message or "Connected to event stream"
            })
            yield f"data: {init_data}\n\n"

            while True:
                data = await queue.get()
                yield f"data: {json.dumps(data)}\n\n"
                if data.get("status") in ["completed", "error"]:
                    break
        finally:
            if queue in job["event_queues"]:
                job["event_queues"].remove(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/jobs/{job_id}/result")
async def get_job_result(job_id: str):
    """Fetch complete extraction and classification results for a job."""
    job = JOBS_STORE.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.get("result"):
        raise HTTPException(status_code=400, detail="Job processing not finished or resulted in error.")
    return job["result"]


@router.post("/override")
async def override_category(req: OverrideRequest):
    """Allow user to manually correct a transaction category, recording override for ML learning."""
    job = JOBS_STORE.get(req.job_id)
    if not job or not job.get("result"):
        raise HTTPException(status_code=404, detail="Job or result not found")

    target_txn = None
    for t in job["result"].transactions:
        if t.id == req.txn_id:
            target_txn = t
            break

    if not target_txn:
        raise HTTPException(status_code=404, detail="Transaction ID not found")

    # Update category
    target_txn.category = req.category
    target_txn.category_confidence = 1.0
    target_txn.classification_source = "manual"

    # Persist in learning loop
    record_user_override(target_txn.description, req.category)

    # Recompute analytics aggregates
    job["result"].analytics = compute_analytics(job["result"].transactions, job["result"].account)

    return {
        "status": "success",
        "message": "Category updated and recorded for continuous model learning.",
        "transaction": target_txn
    }


@router.post("/retrain")
async def retrain_model_endpoint():
    """Retrain the ML classifier with current seed data and manual user overrides."""
    try:
        acc = train_model()
        return {
            "status": "success",
            "accuracy": round(acc, 4),
            "message": f"ML model retrained successfully. Hold-out accuracy: {acc * 100:.2f}%"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export/csv")
async def export_csv_endpoint(job_id: str):
    """Export processed transactions to CSV."""
    job = JOBS_STORE.get(job_id)
    if not job or not job.get("result"):
        raise HTTPException(status_code=404, detail="Job result not found")

    csv_bytes = export_to_csv(job["result"].transactions)
    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=statement_{job_id[:8]}.csv"}
    )


@router.get("/export/xlsx")
async def export_xlsx_endpoint(job_id: str):
    """Export processed transactions to multi-sheet formatted Excel."""
    job = JOBS_STORE.get(job_id)
    if not job or not job.get("result"):
        raise HTTPException(status_code=404, detail="Job result not found")

    xlsx_bytes = export_to_excel(
        account=job["result"].account,
        transactions=job["result"].transactions,
        validation=job["result"].validation
    )
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=statement_{job_id[:8]}.xlsx"}
    )


@router.get("/page-image/{job_id}/{filename}/{page_num}")
async def get_page_image(
    job_id: str,
    filename: str,
    page_num: int,
    highlight: Optional[str] = None
):
    """
    Render PDF page to PNG with optional bounding box highlight overlay.
    Highlight format: x0,top,x1,bottom in 72 DPI points.
    """
    job = JOBS_STORE.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Find file path
    file_path = None
    for f in job["files_data"]:
        if f["name"] == filename:
            file_path = f["path"]
            break

    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="PDF file not found")

    pwd = get_file_password(filename, job["settings"].passwords)
    try:
        raw_png = render_page_to_bytes(file_path, page_num, dpi=150, password=pwd)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to render page: {e}")

    # Draw highlight bounding box if requested
    if highlight:
        try:
            coords = [float(x.strip()) for x in highlight.split(",")]
            if cv2 is not None and len(coords) == 4:
                scale = 150.0 / 72.0
                x0 = int(coords[0] * scale)
                top = int(coords[1] * scale)
                x1 = int(coords[2] * scale)
                bottom = int(coords[3] * scale)

                # Decode PNG
                nparr = np.frombuffer(raw_png, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

                # Draw glowing translucent bounding box
                overlay = img.copy()
                cv2.rectangle(overlay, (max(0, x0 - 4), max(0, top - 2)), (min(img.shape[1], x1 + 4), min(img.shape[0], bottom + 2)), (0, 165, 255), -1)
                cv2.addWeighted(overlay, 0.25, img, 0.75, 0, img)
                cv2.rectangle(img, (max(0, x0 - 4), max(0, top - 2)), (min(img.shape[1], x1 + 4), min(img.shape[0], bottom + 2)), (0, 140, 255), 2)

                is_success, buffer = cv2.imencode(".png", img)
                if is_success:
                    raw_png = buffer.tobytes()
        except Exception:
            pass

    return Response(content=raw_png, media_type="image/png")


@router.post("/demo")
async def load_demo_statement(background_tasks: BackgroundTasks):
    """
    Instantly runs a built-in synthetic statement through the entire pipeline
    for zero-friction instant demo testing.
    """
    demo_pdf = os.path.join(SAMPLES_DIR, "sample_1_hdfc.pdf")
    if not os.path.exists(demo_pdf):
        raise HTTPException(status_code=500, detail="Demo statement sample not found on disk.")

    files = [{
        "name": "sample_1_hdfc.pdf",
        "path": demo_pdf,
        "size": os.path.getsize(demo_pdf)
    }]
    settings = ProcessingSettings(dedupe=True, merge_files=True)
    job_id = create_job(files, settings)
    background_tasks.add_task(process_job_pipeline, job_id)

    return {"job_id": job_id, "status": "queued", "demo": True}
