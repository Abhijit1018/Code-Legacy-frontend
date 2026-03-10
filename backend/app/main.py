"""
main.py — FastAPI application entry point.

Run with:
    uvicorn backend.app.main:app --reload --port 8000
"""

import sys
import os
import logging

# Ensure the project root is on sys.path so `scaledown` and
# `legacy_modernizer` can be imported when running from /backend.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.routes.analysis import router as analysis_router

# Load .env from project root
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)

app = FastAPI(
    title="Legacy Modernizer API",
    description=(
        "AI-powered legacy code analysis and modernisation engine. "
        "Uses Scaledown for context optimisation and OpenRouter LLMs "
        "for code generation."
    ),
    version="0.1.0",
)

# CORS — allow the React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routes
app.include_router(analysis_router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok"}
