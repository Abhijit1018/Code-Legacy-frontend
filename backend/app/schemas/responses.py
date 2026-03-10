"""
Response schemas for the Legacy Modernizer API.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class StatsResponse(BaseModel):
    files_scanned: int = 0
    functions_found: int = 0
    languages_detected: list[str] = Field(default_factory=list)
    context_chars: int = 0
    compressed_chars: int = 0
    compression_savings_percent: float = 0.0


class FileResultResponse(BaseModel):
    """Result for a single converted file."""
    file_path: str = ""
    program_id: str = ""
    python_code: str = ""
    go_code: str = ""
    summary: str = ""
    documentation: str = ""
    original_code: str = ""
    error: str = ""


class ResultsResponse(BaseModel):
    summary: str = ""
    dependency_explanation: str = ""
    python_code: str = ""
    go_code: str = ""
    original_code: dict[str, str] = Field(default_factory=dict)
    documentation: str = ""
    per_file_results: list[FileResultResponse] = Field(default_factory=list)


class LLMInfoResponse(BaseModel):
    model_used: str = ""
    tokens_used: int = 0


class ModernizationResponse(BaseModel):
    """Top-level API response for analysis/conversion endpoints."""

    repo_url: str = ""
    stats: StatsResponse = Field(default_factory=StatsResponse)
    results: ResultsResponse = Field(default_factory=ResultsResponse)
    llm: LLMInfoResponse = Field(default_factory=LLMInfoResponse)


class HealthResponse(BaseModel):
    status: str = "ok"
