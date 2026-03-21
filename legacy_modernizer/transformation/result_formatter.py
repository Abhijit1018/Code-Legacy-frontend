"""
ResultFormatter — convert internal ``ModernizationResult`` objects
into API-friendly dictionaries.

Phase 6 update: includes Phase 1/2/3 outputs.
"""

from __future__ import annotations

from legacy_modernizer.transformation.code_generator import ModernizationResult


class ResultFormatter:
    """Format modernisation results for the REST API layer."""

    @staticmethod
    def to_dict(result: ModernizationResult) -> dict:
        """Serialise a ``ModernizationResult`` to a plain dictionary."""
        # Build per-file results with validation
        per_file = []
        for fr in getattr(result, "per_file_results", []):
            file_entry = {
                "file_path": fr.file_path,
                "program_id": fr.program_id,
                "python_code": fr.python_code,
                "go_code": fr.go_code,
                "summary": fr.summary,
                "documentation": fr.documentation,
                "original_code": fr.original_code,
                "error": fr.error,
            }
            # Include validation if present
            if fr.validation:
                file_entry["validation"] = {
                    "file_path": fr.validation.file_path,
                    "target_language": fr.validation.target_language,
                    "passed": fr.validation.passed,
                    "errors": fr.validation.errors,
                    "warnings": fr.validation.warnings,
                    "retry_count": fr.validation.retry_count,
                }
            else:
                file_entry["validation"] = None
            per_file.append(file_entry)

        # Build validation report
        validation_report = []
        for v in getattr(result, "validation_results", []):
            validation_report.append({
                "file_path": v.file_path,
                "target_language": v.target_language,
                "passed": v.passed,
                "errors": v.errors,
                "warnings": v.warnings,
                "retry_count": v.retry_count,
            })

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
                "per_file_results": per_file,
            },
            "llm": {
                "model_used": result.model_used,
                "tokens_used": result.tokens_used,
            },
            # Phase 1 outputs
            "repo_philosophy": getattr(result, "repo_philosophy", {}),
            "dependency_graph": getattr(result, "dependency_graph_json", {}),
            "file_mapping": getattr(result, "file_mapping", {}),
            # Phase 2 outputs
            "validation_report": validation_report,
            # Phase 3 outputs
            "workflows": getattr(result, "workflow_files", []),
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
