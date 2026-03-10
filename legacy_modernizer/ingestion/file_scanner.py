"""
FileScanner — recursively walk a repository directory and catalogue source files.

Supports detection of legacy languages (COBOL, older Java) as well as common
modern languages.
"""

from __future__ import annotations

import os
import logging
from pathlib import Path
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Mapping of file extensions to language identifiers
EXTENSION_MAP: dict[str, str] = {
    # Legacy
    ".cob": "cobol",
    ".cbl": "cobol",
    ".cobol": "cobol",
    ".cpy": "cobol",
    # Java
    ".java": "java",
    # Python
    ".py": "python",
    # Go
    ".go": "go",
    # C / C++
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    # Fortran
    ".f": "fortran",
    ".f90": "fortran",
    ".for": "fortran",
    # PL/I
    ".pli": "pli",
    # RPG
    ".rpg": "rpg",
    ".rpgle": "rpg",
    # SQL
    ".sql": "sql",
    # Shell
    ".sh": "shell",
    ".bash": "shell",
    # XML / Config
    ".xml": "xml",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
}

# Directories to skip during scanning
SKIP_DIRS: set[str] = {
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    "vendor", "target", "build", "dist", ".idea", ".vscode",
}


@dataclass
class SourceFile:
    """Represents a single discovered source file."""
    path: Path
    relative_path: str
    language: str
    size_bytes: int

    def read(self) -> str:
        """Return the file contents as a string (UTF-8, ignoring errors)."""
        return self.path.read_text(encoding="utf-8", errors="replace")


@dataclass
class ScanResult:
    """Aggregated result of a repository scan."""
    root: Path
    files: list[SourceFile] = field(default_factory=list)
    language_stats: dict[str, int] = field(default_factory=dict)

    @property
    def total_files(self) -> int:
        return len(self.files)

    def files_by_language(self, lang: str) -> list[SourceFile]:
        return [f for f in self.files if f.language == lang]


class FileScanner:
    """Walk a directory tree and collect source files with language metadata."""

    def __init__(
        self,
        extensions: dict[str, str] | None = None,
        skip_dirs: set[str] | None = None,
        max_file_size_kb: int = 512,
    ):
        """
        Args:
            extensions: Override the default extension→language map.
            skip_dirs:  Override the default set of directories to skip.
            max_file_size_kb: Ignore files larger than this (KB).
        """
        self.extensions = extensions or EXTENSION_MAP
        self.skip_dirs = skip_dirs or SKIP_DIRS
        self.max_file_size = max_file_size_kb * 1024

    def scan(self, root: Path | str) -> ScanResult:
        """Recursively scan *root* and return a `ScanResult`."""
        root = Path(root)
        result = ScanResult(root=root)

        for dirpath, dirnames, filenames in os.walk(root):
            # Prune skippable directories in-place
            dirnames[:] = [d for d in dirnames if d not in self.skip_dirs]

            for fname in filenames:
                fpath = Path(dirpath) / fname
                ext = fpath.suffix.lower()

                if ext not in self.extensions:
                    continue

                try:
                    size = fpath.stat().st_size
                except OSError:
                    continue

                if size > self.max_file_size:
                    logger.debug("Skipping large file: %s (%d KB)", fpath, size // 1024)
                    continue

                lang = self.extensions[ext]
                relative = str(fpath.relative_to(root))
                sf = SourceFile(
                    path=fpath,
                    relative_path=relative,
                    language=lang,
                    size_bytes=size,
                )
                result.files.append(sf)
                result.language_stats[lang] = result.language_stats.get(lang, 0) + 1

        logger.info(
            "Scanned %s — %d files across %d language(s)",
            root, result.total_files, len(result.language_stats),
        )
        return result
