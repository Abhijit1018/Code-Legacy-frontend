"""
ResultFormatter — convert internal `ModernizationResult` objects
into API-friendly dictionaries.
"""

from __future__ import annotations

from legacy_modernizer.transformation.code_generator import ModernizationResult


class ResultFormatter:
    """Format modernisation results for the REST API layer."""

    @staticmethod
    def to_dict(result: ModernizationResult) -> dict:
        """Serialise a `ModernizationResult` to a plain dictionary."""
        return {
            "repo_url": result.repo_url,
            "stats": {
                "files_scanned": result.files_scanned,
                "functions_found": result.functions_found,
                "languages_detected": result.languages_detected,
                "context_chars": result.context_chars,
                "compressed_chars": result.compressed_chars,
                "compression_savings_percent": round(
                    result.compression_savings_percent, 2
                ),
            },
            "results": {
                "summary": result.summary,
                "dependency_explanation": result.dependency_explanation,
                "python_code": result.python_code,
                "go_code": result.go_code,
                "original_code": result.original_code,
                "documentation": result.documentation,
                "per_file_results": [
                    {
                        "file_path": fr.file_path,
                        "program_id": fr.program_id,
                        "python_code": fr.python_code,
                        "go_code": fr.go_code,
                        "summary": fr.summary,
                        "documentation": fr.documentation,
                        "original_code": fr.original_code,
                        "error": fr.error,
                    }
                    for fr in getattr(result, "per_file_results", [])
                ],
            },
            "llm": {
                "model_used": result.model_used,
                "tokens_used": result.tokens_used,
            },
        }

    @staticmethod
    def to_summary(result: ModernizationResult) -> dict:
        """Return a lightweight summary (no generated code)."""
        return {
            "repo_url": result.repo_url,
            "files_scanned": result.files_scanned,
            "functions_found": result.functions_found,
            "languages_detected": result.languages_detected,
            "summary": result.summary,
            "compression_savings_percent": round(
                result.compression_savings_percent, 2
            ),
        }
