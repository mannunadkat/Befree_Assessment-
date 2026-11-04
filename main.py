"""FastAPI main entrypoint for Bank Statement Processing & Classification System."""

import os
import logging
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router
from core.ocr_extractor import is_tesseract_available


# Configure application logging
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    filename="logs/app.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("bank_statement_app")

app = FastAPI(
    title="Bank Statement Processing & Classification System",
    description="Automated bank statement data extraction, non-LLM transaction classification, and financial reconciliation.",
    version="1.0.0"
)

# Enable CORS for local development and offline frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routes
app.include_router(router)

# Mount Static directory
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def serve_index():
    """Serve single-page frontend application."""
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "Bank Statement Processing API is running. Access /docs for OpenAPI specifications."}


@app.get("/api/health")
async def health_check():
    """Check backend operational health and OCR availability."""
    tess_ok = is_tesseract_available()
    return {
        "status": "healthy",
        "tesseract_installed": tess_ok,
        "tesseract_status": "Ready" if tess_ok else "Not installed (scanned PDFs will notify user with install instructions)"
    }


# Standard JSON error response handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    logger.error(f"Unhandled error on {request.url.path}: {exc}\n{traceback.format_exc()}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "InternalServerError",
            "message": str(exc)
        }
    )


@app.on_event("startup")
async def on_startup():
    logger.info("Bank Statement System initialized.")
    if is_tesseract_available():
        logger.info("Tesseract OCR binary found and ready.")
    else:
        logger.warning("Tesseract OCR binary not detected in PATH.")
