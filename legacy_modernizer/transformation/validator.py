"""
Validator — post-translation validation for generated code.

After each file is translated by the LLM, validates the output:
  • **Python**: ``py_compile`` check + optional ``mypy`` type checking.
  • **Go**: write to temp dir and run ``go build``.

Provides retry logic by building a fix prompt from validation errors.
"""

from __future__ import annotations

import os
import py_compile
import tempfile
import subprocess
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Data classes
# ------------------------------------------------------------------

@dataclass
class FileValidationResult:
    """Validation outcome for a single translated file."""
    file_path: str = ""
    target_language: str = ""
    passed: bool = False
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    retry_count: int = 0


# ------------------------------------------------------------------
# Validator
# ------------------------------------------------------------------

class TranslationValidator:
    """
    Validate translated code for syntax and type correctness.

    Usage::

        validator = TranslationValidator()
        result = validator.validate(code, "python", "my_file.py")
        if not result.passed:
            fix_prompt = validator.build_fix_prompt(code, result)
    """

    def __init__(self, use_mypy: bool = False):
        """
        Args:
            use_mypy: If True, also run mypy on Python files (slower but
                      catches type errors). Requires mypy to be installed.
        """
        self._use_mypy = use_mypy

    def validate(
        self,
        code: str,
        target_language: str,
        file_path: str = "",
    ) -> FileValidationResult:
        """
        Validate translated *code* for the given *target_language*.

        Returns a ``FileValidationResult`` with ``passed=True`` if clean.
        """
        result = FileValidationResult(
            file_path=file_path,
            target_language=target_language,
        )

        if not code or not code.strip():
            result.errors.append("Empty or whitespace-only code")
            return result

        handler = {
            "python": self._validate_python,
            "go": self._validate_go,
        }.get(target_language.lower())

        if handler is None:
            # No validator for this language — pass by default
            result.passed = True
            result.warnings.append(
                f"No validator available for {target_language}"
            )
            return result

        return handler(code, file_path, result)

    def build_fix_prompt(
        self,
        code: str,
        validation_result: FileValidationResult,
    ) -> str:
        """
        Build an LLM prompt that asks the model to fix the validation errors.
        """
        errors_text = "\n".join(
            f"  - {e}" for e in validation_result.errors
        )
        return (
            f"The following {validation_result.target_language} code has "
            f"validation errors. Fix ALL errors and return ONLY the corrected "
            f"code (no explanations, no JSON wrapping).\n\n"
            f"=== ERRORS ===\n{errors_text}\n\n"
            f"=== CODE TO FIX ===\n{code}\n\n"
            f"Return the fixed code only."
        )

    # ------------------------------------------------------------------
    # Python validation
    # ------------------------------------------------------------------

    def _validate_python(
        self,
        code: str,
        file_path: str,
        result: FileValidationResult,
    ) -> FileValidationResult:
        """Validate Python via py_compile and optionally mypy."""
        # Write to temp file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(code)
            tmp_path = f.name

        try:
            # 1. py_compile check
            try:
                py_compile.compile(tmp_path, doraise=True)
            except py_compile.PyCompileError as exc:
                result.errors.append(f"SyntaxError: {exc}")
                return result

            # 2. Optional mypy check
            if self._use_mypy:
                mypy_errors = self._run_mypy(tmp_path)
                if mypy_errors:
                    result.errors.extend(mypy_errors)
                    return result

            result.passed = True
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        return result

    @staticmethod
    def _run_mypy(file_path: str) -> list[str]:
        """Run mypy on a file and return any error messages."""
        try:
            proc = subprocess.run(
                ["mypy", "--ignore-missing-imports", "--no-error-summary", file_path],
                capture_output=True, text=True, timeout=30,
            )
            if proc.returncode != 0:
                errors = [
                    line for line in proc.stdout.splitlines()
                    if ": error:" in line
                ]
                return errors if errors else [proc.stdout[:500]]
        except FileNotFoundError:
            # mypy not installed — skip
            pass
        except subprocess.TimeoutExpired:
            return ["mypy timed out after 30s"]
        return []

    # ------------------------------------------------------------------
    # Go validation
    # ------------------------------------------------------------------

    def _validate_go(
        self,
        code: str,
        file_path: str,
        result: FileValidationResult,
    ) -> FileValidationResult:
        """Validate Go by writing to a temp dir and running go build."""
        tmp_dir = tempfile.mkdtemp(prefix="go_validate_")
        go_file = os.path.join(tmp_dir, "main.go")

        try:
            with open(go_file, "w", encoding="utf-8") as f:
                f.write(code)

            # Initialize a Go module
            subprocess.run(
                ["go", "mod", "init", "validator_tmp"],
                cwd=tmp_dir, capture_output=True, text=True, timeout=15,
            )

            # Try to build
            proc = subprocess.run(
                ["go", "build", "./..."],
                cwd=tmp_dir, capture_output=True, text=True, timeout=30,
            )

            if proc.returncode != 0:
                errors = proc.stderr.strip().splitlines()
                result.errors.extend(errors[:10])  # Cap at 10 errors
                return result

            result.passed = True

        except FileNotFoundError:
            result.warnings.append("Go compiler not found — skipping validation")
            result.passed = True  # Can't validate, pass by default
        except subprocess.TimeoutExpired:
            result.errors.append("Go build timed out after 30s")
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)

        return result
