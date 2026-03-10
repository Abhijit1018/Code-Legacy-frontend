"""
ASTParser — Extract functions, classes, imports, and call-sites from source code.

Supports Python and Java via the built-in `ast` module (Python) and a
lightweight regex/heuristic approach (Java, COBOL, and other languages).
"""

from __future__ import annotations

import ast
import re
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class FunctionInfo:
    """Metadata about a single function / method / paragraph."""
    name: str
    file_path: str
    start_line: int
    end_line: int
    calls: list[str] = field(default_factory=list)
    language: str = "unknown"
    body: str = ""


@dataclass
class ParseResult:
    """Container for all entities extracted from a single file."""
    file_path: str
    language: str
    functions: list[FunctionInfo] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    classes: list[str] = field(default_factory=list)


class ASTParser:
    """Language-aware source-code parser that extracts structural information."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse(self, source: str, file_path: str, language: str) -> ParseResult:
        """
        Parse *source* and return structured metadata.

        Dispatches to the appropriate language-specific parser.
        """
        handler = {
            "python": self._parse_python,
            "java": self._parse_java,
            "cobol": self._parse_cobol,
        }.get(language, self._parse_generic)

        try:
            return handler(source, file_path, language)
        except Exception as exc:
            logger.warning("Parsing failed for %s: %s", file_path, exc)
            return ParseResult(file_path=file_path, language=language)

    # ------------------------------------------------------------------
    # Python parser (full AST)
    # ------------------------------------------------------------------

    def _parse_python(self, source: str, file_path: str, language: str) -> ParseResult:
        result = ParseResult(file_path=file_path, language=language)
        tree = ast.parse(source, filename=file_path)
        lines = source.splitlines()

        for node in ast.walk(tree):
            # Imports
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    result.imports.append(alias.name)

            # Classes
            elif isinstance(node, ast.ClassDef):
                result.classes.append(node.name)

            # Functions / methods
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                calls = self._extract_python_calls(node)
                start = node.lineno - 1
                end = node.end_lineno if node.end_lineno else start + 1
                body = "\n".join(lines[start:end])

                result.functions.append(FunctionInfo(
                    name=node.name,
                    file_path=file_path,
                    start_line=node.lineno,
                    end_line=end,
                    calls=calls,
                    language=language,
                    body=body,
                ))

        return result

    @staticmethod
    def _extract_python_calls(node: ast.AST) -> list[str]:
        """Walk *node* and collect names of all function calls."""
        calls: list[str] = []
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    calls.append(child.func.id)
                elif isinstance(child.func, ast.Attribute):
                    calls.append(child.func.attr)
        return calls

    # ------------------------------------------------------------------
    # Java parser (regex heuristic)
    # ------------------------------------------------------------------

    _JAVA_METHOD_RE = re.compile(
        r"(?:public|private|protected|static|\s)+"
        r"[\w<>\[\]]+\s+"       # return type
        r"(\w+)\s*\([^)]*\)\s*" # method name + params
        r"\{",
        re.MULTILINE,
    )
    _JAVA_CALL_RE = re.compile(r"(\w+)\s*\(")
    _JAVA_IMPORT_RE = re.compile(r"import\s+([\w.]+);")
    _JAVA_CLASS_RE = re.compile(r"class\s+(\w+)")

    def _parse_java(self, source: str, file_path: str, language: str) -> ParseResult:
        result = ParseResult(file_path=file_path, language=language)
        lines = source.splitlines()

        result.imports = self._JAVA_IMPORT_RE.findall(source)
        result.classes = self._JAVA_CLASS_RE.findall(source)

        for m in self._JAVA_METHOD_RE.finditer(source):
            name = m.group(1)
            start_line = source[:m.start()].count("\n") + 1
            # Find matching closing brace (simple brace-counting)
            end_line = self._find_brace_end(lines, start_line - 1)
            body = "\n".join(lines[start_line - 1 : end_line])
            calls = [c for c in self._JAVA_CALL_RE.findall(body) if c != name]

            result.functions.append(FunctionInfo(
                name=name,
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                calls=calls,
                language=language,
                body=body,
            ))

        return result

    _COBOL_PROGRAM_ID_RE = re.compile(r"PROGRAM-ID\.\s+([\w-]+)", re.IGNORECASE)
    _COBOL_CALL_RE = re.compile(r"CALL\s+['\"]?([\w-]+)", re.IGNORECASE)

    def _parse_cobol(self, source: str, file_path: str, language: str) -> ParseResult:
        result = ParseResult(file_path=file_path, language=language)
        lines = source.splitlines()

        # Extract PROGRAM-ID to use as the function/module name
        prog_match = self._COBOL_PROGRAM_ID_RE.search(source)
        prog_name = prog_match.group(1) if prog_match else Path(file_path).stem

        # Extract cross-program dependencies (ignoring PERFORM which is internal procedural logic)
        calls = list(set(self._COBOL_CALL_RE.findall(source)))

        # Treat the entire COBOL program as a single contextual unit
        # so the LLM can understand the global workflow, variables, and logic combined.
        result.functions.append(FunctionInfo(
            name=prog_name,
            file_path=file_path,
            start_line=1,
            end_line=len(lines),
            calls=calls,
            language=language,
            body=source,
        ))

        return result

    # ------------------------------------------------------------------
    # Generic / fallback parser
    # ------------------------------------------------------------------

    _GENERIC_FUNC_RE = re.compile(
        r"(?:func|function|def|sub|procedure)\s+(\w+)", re.IGNORECASE
    )

    def _parse_generic(self, source: str, file_path: str, language: str) -> ParseResult:
        result = ParseResult(file_path=file_path, language=language)
        for m in self._GENERIC_FUNC_RE.finditer(source):
            start = source[:m.start()].count("\n") + 1
            result.functions.append(FunctionInfo(
                name=m.group(1),
                file_path=file_path,
                start_line=start,
                end_line=start,
                language=language,
            ))
        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _find_brace_end(lines: list[str], start_idx: int) -> int:
        """Return the 1-based line number of the closing brace."""
        depth = 0
        for i in range(start_idx, len(lines)):
            depth += lines[i].count("{") - lines[i].count("}")
            if depth <= 0:
                return i + 1
        return len(lines)
