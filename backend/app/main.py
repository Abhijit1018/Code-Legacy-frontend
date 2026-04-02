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

SCALEDOWN_ROOT = os.path.join(PROJECT_ROOT, "scaledown")
if SCALEDOWN_ROOT not in sys.path:
    sys.path.insert(0, SCALEDOWN_ROOT)

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load .env from project root before importing routes/services.
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from backend.app.routes.analysis import router as analysis_router

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


@app.get("/")
async def root():
    return {
        "status": "ok",
        "service": "Legacy Modernizer API",
        "docs": "/docs",
    }


@app.api_route("/health", methods=["GET", "HEAD"])
async def health():
    return {"status": "ok"}
