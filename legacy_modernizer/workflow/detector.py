"""
WorkflowDetector — scan a repository for legacy workflow artifacts.

Detects:
  • JCL jobs (``*.jcl``, ``*.jcls``)
  • Build configs (Ant ``build.xml``, Maven ``pom.xml``, Gradle ``build.gradle``)
  • Shell scripts (``*.sh``, ``*.bash``, ``*.bat``, ``*.cmd``)
  • Cron definitions (``crontab``, files containing cron patterns)
  • Config files (``.properties``, ``.ini``, ``.cfg``, ``.xml``, ``.env``)
  • Makefiles
"""

from __future__ import annotations

import os
import re
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Data classes
# ------------------------------------------------------------------

@dataclass
class WorkflowStep:
    """A single step in a detected workflow."""
    step_number: int = 0
    action: str = ""           # e.g. "execute program", "copy file", "sort"
    target: str = ""           # program or file involved
    description: str = ""


@dataclass
class DetectedWorkflow:
    """A legacy workflow detected in the repository."""
    workflow_type: str = ""    # "jcl", "ant", "maven", "shell", "cron", "makefile"
    source_file: str = ""      # relative path to the source file
    name: str = ""             # job name or script name
    steps: list[WorkflowStep] = field(default_factory=list)
    description: str = ""
    raw_content: str = ""


# ------------------------------------------------------------------
# Detection patterns
# ------------------------------------------------------------------

JCL_PATTERNS = {
    "job": re.compile(r"//(\w+)\s+JOB\b", re.IGNORECASE),
    "exec": re.compile(r"//\w+\s+EXEC\s+(PGM=|PROC=)?(\w+)", re.IGNORECASE),
    "dd": re.compile(r"//(\w+)\s+DD\s+DSN=([^\s,]+)", re.IGNORECASE),
}

CRON_PATTERN = re.compile(
    r"^\s*(?:\S+\s+){5}\S+",  # 5 time fields + command
    re.MULTILINE,
)

WORKFLOW_FILE_PATTERNS: dict[str, list[str]] = {
    "jcl": ["*.jcl", "*.jcls"],
    "ant": ["build.xml"],
    "maven": ["pom.xml"],
    "gradle": ["build.gradle", "build.gradle.kts"],
    "makefile": ["Makefile", "makefile", "GNUmakefile"],
    "shell": ["*.sh", "*.bash", "*.bat", "*.cmd"],
    "cron": ["crontab", "crontab.*"],
    "config": ["*.properties", "*.ini", "*.cfg"],
}


# ------------------------------------------------------------------
# Detector
# ------------------------------------------------------------------

class WorkflowDetector:
    """Scan a repository directory for legacy workflow artifacts."""

    def detect(self, repo_root: Path | str) -> list[DetectedWorkflow]:
        """
        Walk the repo and detect all legacy workflow files.

        Returns a list of ``DetectedWorkflow`` objects.
        """
        repo_root = Path(repo_root)
        workflows: list[DetectedWorkflow] = []

        for dirpath, dirnames, filenames in os.walk(repo_root):
            # Skip common noise directories
            dirnames[:] = [
                d for d in dirnames
                if d not in {".git", "__pycache__", "node_modules", ".venv", "venv"}
            ]

            for fname in filenames:
                fpath = Path(dirpath) / fname
                rel_path = str(fpath.relative_to(repo_root))

                wf = self._classify_file(fpath, rel_path)
                if wf:
                    workflows.append(wf)

        logger.info("Detected %d workflow artifacts", len(workflows))
        return workflows

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    def _classify_file(self, fpath: Path, rel_path: str) -> DetectedWorkflow | None:
        """Attempt to classify a file as a workflow artifact."""
        name = fpath.name.lower()
        ext = fpath.suffix.lower()

        # JCL
        if ext in (".jcl", ".jcls"):
            return self._parse_jcl(fpath, rel_path)

        # Build systems
        if name == "build.xml":
            return DetectedWorkflow(
                workflow_type="ant", source_file=rel_path,
                name="Ant Build", description="Apache Ant build configuration",
            )
        if name == "pom.xml":
            return DetectedWorkflow(
                workflow_type="maven", source_file=rel_path,
                name="Maven Build", description="Apache Maven project configuration",
            )
        if name in ("build.gradle", "build.gradle.kts"):
            return DetectedWorkflow(
                workflow_type="gradle", source_file=rel_path,
                name="Gradle Build", description="Gradle build configuration",
            )

        # Makefiles
        if name in ("makefile", "gnumakefile") or name.startswith("makefile"):
            return DetectedWorkflow(
                workflow_type="makefile", source_file=rel_path,
                name="Makefile", description="Make build system",
            )

        # Shell scripts
        if ext in (".sh", ".bash", ".bat", ".cmd"):
            return self._parse_shell(fpath, rel_path)

        # Cron
        if "crontab" in name:
            return self._parse_cron(fpath, rel_path)

        # Config files
        if ext in (".properties", ".ini", ".cfg"):
            return DetectedWorkflow(
                workflow_type="config", source_file=rel_path,
                name=fpath.stem, description=f"Configuration file ({ext})",
            )

        return None

    # ------------------------------------------------------------------
    # Parsers
    # ------------------------------------------------------------------

    def _parse_jcl(self, fpath: Path, rel_path: str) -> DetectedWorkflow:
        """Parse a JCL file to extract job name and steps."""
        try:
            content = fpath.read_text(encoding="utf-8", errors="replace")
        except Exception:
            content = ""

        wf = DetectedWorkflow(
            workflow_type="jcl", source_file=rel_path,
            raw_content=content,
        )

        # Extract job name
        job_match = JCL_PATTERNS["job"].search(content)
        wf.name = job_match.group(1) if job_match else fpath.stem

        # Extract EXEC steps
        for i, m in enumerate(JCL_PATTERNS["exec"].finditer(content), 1):
            program = m.group(2)
            step_type = "procedure" if m.group(1) and "PROC" in m.group(1).upper() else "program"
            wf.steps.append(WorkflowStep(
                step_number=i,
                action=f"execute {step_type}",
                target=program,
                description=f"Run {step_type} {program}",
            ))

        wf.description = (
            f"JCL job '{wf.name}' with {len(wf.steps)} execution step(s)"
        )
        return wf

    def _parse_shell(self, fpath: Path, rel_path: str) -> DetectedWorkflow:
        """Parse a shell script for basic step detection."""
        try:
            content = fpath.read_text(encoding="utf-8", errors="replace")
        except Exception:
            content = ""

        return DetectedWorkflow(
            workflow_type="shell", source_file=rel_path,
            name=fpath.stem, raw_content=content,
            description=f"Shell script ({fpath.suffix})",
        )

    def _parse_cron(self, fpath: Path, rel_path: str) -> DetectedWorkflow:
        """Parse a crontab file."""
        try:
            content = fpath.read_text(encoding="utf-8", errors="replace")
        except Exception:
            content = ""

        steps = []
        for i, m in enumerate(CRON_PATTERN.finditer(content), 1):
            line = m.group(0).strip()
            if line.startswith("#"):
                continue
            steps.append(WorkflowStep(
                step_number=i, action="scheduled command",
                target=line, description=f"Cron entry: {line[:80]}",
            ))

        return DetectedWorkflow(
            workflow_type="cron", source_file=rel_path,
            name="crontab", steps=steps, raw_content=content,
            description=f"Cron schedule with {len(steps)} entries",
        )
