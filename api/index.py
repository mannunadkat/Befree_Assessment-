"""Vercel serverless function entrypoint for FastAPI."""
import os
import sys

# Add repository root to python search path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Set TESSDATA_PREFIX to bundled language models
os.environ["TESSDATA_PREFIX"] = os.path.join(ROOT_DIR, "tessdata")

from main import app

