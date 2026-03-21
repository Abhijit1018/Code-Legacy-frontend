"""
Response schemas for the Legacy Modernizer API.

Phase 6 update: expanded with repo_philosophy, dependency_graph,
file_mapping, workflows, and validation_report fields.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class StatsResponse(BaseModel):
    """Statistics about the analysed repository."""
    files_scanned: int = Field(0, description="Total files scanned in the repository")
    functions_found: int = Field(0, description="Total functions/methods extracted")
    languages_detected: list[str] = Field(default_factory=list, description="Languages found in the repo")
    context_chars: int = Field(0, description="Total characters of raw context")
    compressed_chars: int = Field(0, description="Characters after compression")
    compression_savings_percent: float = Field(0.0, description="Percentage saved via compression")


class FileValidationResponse(BaseModel):
    """Validation result for a single translated file."""
    file_path: str = Field("", description="Path of the validated file")
    target_language: str = Field("", description="Language the code was translated to")
    passed: bool = Field(False, description="Whether validation passed")
    errors: list[str] = Field(default_factory=list, description="Validation error messages")
    warnings: list[str] = Field(default_factory=list, description="Validation warnings")
    retry_count: int = Field(0, description="Number of LLM retries for this file")


class FileResultResponse(BaseModel):
    """Result for a single converted file."""
    file_path: str = Field("", description="Original file path")
    program_id: str = Field("", description="Program identifier (e.g., COBOL PROGRAM-ID)")
    python_code: str = Field("", description="Generated Python code")
    go_code: str = Field("", description="Generated Go code")
    summary: str = Field("", description="LLM-generated summary of the file")
    documentation: str = Field("", description="LLM-generated documentation")
    original_code: str = Field("", description="Original source code")
    error: str = Field("", description="Error message if conversion failed")
    validation: FileValidationResponse | None = Field(None, description="Validation result for this file")


class WorkflowResponse(BaseModel):
    """Result of a workflow conversion."""
    workflow_type: str = Field("", description="Type: jcl, ant, maven, shell, etc.")
    source_file: str = Field("", description="Original workflow file path")
    modern_file_path: str = Field("", description="Generated modern file path")
    modern_content: str = Field("", description="Content of the generated file")
    description: str = Field("", description="Description of what was converted")


class ResultsResponse(BaseModel):
    """Combined results from all files."""
    summary: str = Field("", description="Combined summary of all translations")
    dependency_explanation: str = Field("", description="Explanation of cross-file dependencies and translation order")
    python_code: str = Field("", description="Combined Python code from all files")
    go_code: str = Field("", description="Combined Go code from all files")
    original_code: dict[str, str] = Field(default_factory=dict, description="Original source code by file path")
    documentation: str = Field("", description="Combined documentation")
    per_file_results: list[FileResultResponse] = Field(default_factory=list, description="Per-file conversion results")


class LLMInfoResponse(BaseModel):
    """Information about LLM usage."""
    model_used: str = Field("", description="LLM model identifier used")
    tokens_used: int = Field(0, description="Total tokens consumed across all calls")


class ModernizationResponse(BaseModel):
    """Top-level API response for analysis/conversion endpoints."""
    repo_url: str = Field("", description="URL of the analysed repository")
    stats: StatsResponse = Field(default_factory=StatsResponse, description="Repository analysis statistics")
    results: ResultsResponse = Field(default_factory=ResultsResponse, description="Translation results")
    llm: LLMInfoResponse = Field(default_factory=LLMInfoResponse, description="LLM usage information")

    # Phase 1 outputs
    repo_philosophy: dict = Field(default_factory=dict, description="Extracted architectural philosophy")
    dependency_graph: dict = Field(default_factory=dict, description="File-level dependency graph (adjacency list)")
    file_mapping: dict[str, str] = Field(default_factory=dict, description="Mapping from original to modernised file paths")

    # Phase 2 outputs
    validation_report: list[FileValidationResponse] = Field(default_factory=list, description="Per-file validation results")

    # Phase 3 outputs
    workflows: list[WorkflowResponse] = Field(default_factory=list, description="Detected and converted workflows")


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = Field("ok", description="Service health status")


class SSEEvent(BaseModel):
    """Server-Sent Event for streaming progress."""
    event_type: str = Field("", description="Event type: phase, file_status, log, complete, error")
    phase: str = Field("", description="Current phase: analyzing, translating, validating, documenting")
    file_path: str = Field("", description="File being processed (if applicable)")
    status: str = Field("", description="Status: queued, processing, passed, failed")
    message: str = Field("", description="Human-readable progress message")
    progress: float = Field(0.0, description="Progress percentage (0-100)")
