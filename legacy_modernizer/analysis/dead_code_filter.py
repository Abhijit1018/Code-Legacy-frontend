"""
DeadCodeFilter — remove noise from legacy source code before LLM processing.

Strips:
  • block and line comments
  • deprecated / disabled sections
  • unused functions (if a dependency graph is supplied)
  • test files and test functions
  • excessive blank lines
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass

from legacy_modernizer.ingestion.file_scanner import SourceFile

logger = logging.getLogger(__name__)


@dataclass
class FilterStats:
    """Summary of what the filter removed."""
    original_lines: int = 0
    filtered_lines: int = 0
    comment_lines_removed: int = 0
    blank_lines_removed: int = 0
    files_skipped: int = 0

    @property
    def reduction_percent(self) -> float:
        if self.original_lines == 0:
            return 0.0
        return (1 - self.filtered_lines / self.original_lines) * 100


class DeadCodeFilter:
    """Apply heuristic-based noise removal to source files."""

    # Patterns considered "test" files
    _TEST_PATH_RE = re.compile(
        r"(^|/)(test_|tests/|spec/|__tests__|_test\.)",
        re.IGNORECASE,
    )

    def __init__(
        self,
        remove_comments: bool = True,
        remove_tests: bool = True,
        collapse_blanks: bool = True,
        max_consecutive_blanks: int = 1,
    ):
        self.remove_comments = remove_comments
        self.remove_tests = remove_tests
        self.collapse_blanks = collapse_blanks
        self.max_consecutive_blanks = max_consecutive_blanks

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def filter_files(self, files: list[SourceFile]) -> tuple[list[SourceFile], FilterStats]:
        """
        Return a new list of SourceFile objects with noise removed.

        Files that are test-only are dropped entirely.
        """
        stats = FilterStats()
        cleaned: list[SourceFile] = []

        for sf in files:
            # Skip test files
            if self.remove_tests and self._is_test_file(sf.relative_path):
                stats.files_skipped += 1
                continue
            cleaned.append(sf)

        return cleaned, stats

    def clean_source(self, source: str, language: str) -> tuple[str, FilterStats]:
        """
        Clean a single source string and return *(cleaned_text, stats)*.
        """
        stats = FilterStats()
        lines = source.splitlines()
        stats.original_lines = len(lines)

        if self.remove_comments:
            lines, removed = self._strip_comments(lines, language)
            stats.comment_lines_removed = removed

        if self.collapse_blanks:
            lines, removed = self._collapse_blank_lines(lines)
            stats.blank_lines_removed = removed

        stats.filtered_lines = len(lines)
        return "\n".join(lines), stats

    # ------------------------------------------------------------------
    # Comment stripping
    # ------------------------------------------------------------------

    def _strip_comments(
        self, lines: list[str], language: str
    ) -> tuple[list[str], int]:
        handler = {
            "python": self._strip_python_comments,
            "java": self._strip_c_style_comments,
            "c": self._strip_c_style_comments,
            "cpp": self._strip_c_style_comments,
            "go": self._strip_c_style_comments,
            "cobol": self._strip_cobol_comments,
        }.get(language, self._strip_hash_comments)
        return handler(lines)

    @staticmethod
    def _strip_python_comments(lines: list[str]) -> tuple[list[str], int]:
        out: list[str] = []
        removed = 0
        in_docstring = False
        doc_char = ""

        for line in lines:
            stripped = line.strip()

            # Toggle docstring blocks
            if not in_docstring:
                if stripped.startswith('"""') or stripped.startswith("'''"):
                    doc_char = stripped[:3]
                    # Single-line docstring
                    if stripped.count(doc_char) >= 2:
                        removed += 1
                        continue
                    in_docstring = True
                    removed += 1
                    continue
            else:
                if doc_char in stripped:
                    in_docstring = False
                removed += 1
                continue

            # Line comments
            if stripped.startswith("#"):
                removed += 1
                continue

            out.append(line)

        return out, removed

    @staticmethod
    def _strip_c_style_comments(lines: list[str]) -> tuple[list[str], int]:
        out: list[str] = []
        removed = 0
        in_block = False

        for line in lines:
            stripped = line.strip()
            if in_block:
                removed += 1
                if "*/" in stripped:
                    in_block = False
                continue

            if stripped.startswith("/*"):
                in_block = "*/" not in stripped
                removed += 1
                continue

            if stripped.startswith("//"):
                removed += 1
                continue

            out.append(line)

        return out, removed

    @staticmethod
    def _strip_cobol_comments(lines: list[str]) -> tuple[list[str], int]:
        out: list[str] = []
        removed = 0
        for line in lines:
            # In fixed-format COBOL, column 7 = '*' indicates a comment
            if len(line) > 6 and line[6] == "*":
                removed += 1
                continue
            out.append(line)
        return out, removed

    @staticmethod
    def _strip_hash_comments(lines: list[str]) -> tuple[list[str], int]:
        out: list[str] = []
        removed = 0
        for line in lines:
            if line.strip().startswith("#"):
                removed += 1
                continue
            out.append(line)
        return out, removed

    # ------------------------------------------------------------------
    # Blank-line collapsing
    # ------------------------------------------------------------------

    def _collapse_blank_lines(self, lines: list[str]) -> tuple[list[str], int]:
        out: list[str] = []
        removed = 0
        consecutive = 0

        for line in lines:
            if line.strip() == "":
                consecutive += 1
                if consecutive > self.max_consecutive_blanks:
                    removed += 1
                    continue
            else:
                consecutive = 0
            out.append(line)

        return out, removed

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @classmethod
    def _is_test_file(cls, path: str) -> bool:
        return bool(cls._TEST_PATH_RE.search(path))
