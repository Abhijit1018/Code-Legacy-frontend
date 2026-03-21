"""
WorkflowConverter — map detected legacy workflows to modern equivalents.

Conversion mapping:
  • JCL jobs → Python scripts / Makefile targets
  • Ant/Maven → Makefile / pyproject.toml
  • Shell scripts → modernised shell or Python scripts
  • Cron → cron-compatible schedule definitions
  • Config files → .env / pyproject.toml sections
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from legacy_modernizer.workflow.detector import DetectedWorkflow

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Data classes
# ------------------------------------------------------------------

@dataclass
class WorkflowResult:
    """A modernised workflow output."""
    original_workflow: DetectedWorkflow | None = None
    modern_file_path: str = ""
    modern_content: str = ""
    workflow_type: str = ""
    description: str = ""


# ------------------------------------------------------------------
# Modernisation mapping
# ------------------------------------------------------------------

MODERNISATION_MAP: dict[str, dict[str, str]] = {
    "jcl": {
        "target_type": "python_script",
        "file_extension": ".py",
        "description": "JCL job converted to Python orchestration script",
    },
    "ant": {
        "target_type": "makefile",
        "file_extension": "",
        "target_name": "Makefile",
        "description": "Ant build converted to Makefile",
    },
    "maven": {
        "target_type": "pyproject",
        "file_extension": ".toml",
        "target_name": "pyproject.toml",
        "description": "Maven POM converted to pyproject.toml",
    },
    "gradle": {
        "target_type": "makefile",
        "file_extension": "",
        "target_name": "Makefile",
        "description": "Gradle build converted to Makefile",
    },
    "shell": {
        "target_type": "python_script",
        "file_extension": ".py",
        "description": "Shell script converted to Python equivalent",
    },
    "makefile": {
        "target_type": "makefile",
        "file_extension": "",
        "description": "Makefile preserved/updated",
    },
    "cron": {
        "target_type": "schedule_config",
        "file_extension": ".yaml",
        "description": "Cron schedule converted to YAML config",
    },
    "config": {
        "target_type": "env_file",
        "file_extension": "",
        "target_name": ".env.example",
        "description": "Config file converted to .env template",
    },
}


# ------------------------------------------------------------------
# Converter
# ------------------------------------------------------------------

class WorkflowConverter:
    """Convert detected workflows to modern equivalents."""

    def convert(self, workflows: list[DetectedWorkflow]) -> list[WorkflowResult]:
        """
        Convert all detected workflows to modern equivalents.

        Returns a list of ``WorkflowResult`` objects with generated content.
        """
        results: list[WorkflowResult] = []

        for wf in workflows:
            handler = {
                "jcl": self._convert_jcl,
                "ant": self._convert_build_system,
                "maven": self._convert_build_system,
                "gradle": self._convert_build_system,
                "shell": self._convert_shell,
                "makefile": self._convert_makefile,
                "cron": self._convert_cron,
                "config": self._convert_config,
            }.get(wf.workflow_type, self._convert_generic)

            result = handler(wf)
            results.append(result)

        logger.info("Converted %d workflows", len(results))
        return results

    # ------------------------------------------------------------------
    # Converters
    # ------------------------------------------------------------------

    def _convert_jcl(self, wf: DetectedWorkflow) -> WorkflowResult:
        """Convert a JCL job to a Python orchestration script."""
        lines = [
            '#!/usr/bin/env python3',
            '"""',
            f'Modernised workflow: {wf.name}',
            f'Original JCL: {wf.source_file}',
            f'Description: {wf.description}',
            '"""',
            '',
            'import subprocess',
            'import sys',
            'import logging',
            '',
            'logging.basicConfig(level=logging.INFO)',
            'logger = logging.getLogger(__name__)',
            '',
            '',
        ]

        if wf.steps:
            lines.append('def main():')
            lines.append(f'    """Execute the {wf.name} workflow."""')
            lines.append(f'    logger.info("Starting workflow: {wf.name}")')
            lines.append('')

            for step in wf.steps:
                lines.append(f'    # Step {step.step_number}: {step.description}')
                lines.append(f'    logger.info("Step {step.step_number}: {step.action} {step.target}")')
                lines.append(f'    # TODO: Implement {step.action} for {step.target}')
                lines.append(f'    # Original: {step.description}')
                lines.append('')

            lines.append(f'    logger.info("Workflow {wf.name} complete")')
            lines.append('')
            lines.append('')
            lines.append('if __name__ == "__main__":')
            lines.append('    main()')
        else:
            lines.append('def main():')
            lines.append(f'    """Execute the {wf.name} workflow."""')
            lines.append('    # TODO: Implement workflow logic')
            lines.append('    pass')
            lines.append('')
            lines.append('')
            lines.append('if __name__ == "__main__":')
            lines.append('    main()')

        content = "\n".join(lines) + "\n"
        file_name = f"workflow_{wf.name.lower().replace(' ', '_').replace('-', '_')}.py"

        return WorkflowResult(
            original_workflow=wf,
            modern_file_path=file_name,
            modern_content=content,
            workflow_type="python_script",
            description=f"JCL job '{wf.name}' → Python script",
        )

    def _convert_build_system(self, wf: DetectedWorkflow) -> WorkflowResult:
        """Convert build system config to a Makefile."""
        mapping = MODERNISATION_MAP.get(wf.workflow_type, {})
        target_name = mapping.get("target_name", "Makefile")

        lines = [
            f'# Modernised from: {wf.source_file}',
            f'# Original type: {wf.workflow_type}',
            '',
            '.PHONY: all build test clean',
            '',
            'all: build',
            '',
            'build:',
            '\t@echo "Building project..."',
            '\t# TODO: Add build commands',
            '',
            'test:',
            '\t@echo "Running tests..."',
            '\tpython -m pytest tests/ -v',
            '',
            'clean:',
            '\t@echo "Cleaning..."',
            '\trm -rf __pycache__ *.pyc build/ dist/',
            '',
        ]

        return WorkflowResult(
            original_workflow=wf,
            modern_file_path=target_name,
            modern_content="\n".join(lines) + "\n",
            workflow_type="makefile",
            description=f"{wf.workflow_type.title()} → Makefile",
        )

    def _convert_shell(self, wf: DetectedWorkflow) -> WorkflowResult:
        """Convert shell script to a Python equivalent."""
        lines = [
            '#!/usr/bin/env python3',
            '"""',
            f'Modernised from: {wf.source_file}',
            f'Original shell script: {wf.name}',
            '"""',
            '',
            'import subprocess',
            'import sys',
            'import os',
            '',
            '',
            'def main():',
            f'    """Run the modernised {wf.name} workflow."""',
            '    # TODO: Convert shell commands to Python equivalents',
            '    pass',
            '',
            '',
            'if __name__ == "__main__":',
            '    main()',
        ]

        file_name = f"{wf.name.lower().replace(' ', '_').replace('-', '_')}.py"
        return WorkflowResult(
            original_workflow=wf,
            modern_file_path=file_name,
            modern_content="\n".join(lines) + "\n",
            workflow_type="python_script",
            description=f"Shell script → Python",
        )

    def _convert_makefile(self, wf: DetectedWorkflow) -> WorkflowResult:
        """Preserve/update an existing Makefile."""
        return WorkflowResult(
            original_workflow=wf,
            modern_file_path="Makefile",
            modern_content="# Preserved from original Makefile\n",
            workflow_type="makefile",
            description="Makefile preserved",
        )

    def _convert_cron(self, wf: DetectedWorkflow) -> WorkflowResult:
        """Convert cron schedule to YAML config."""
        lines = [
            "# Modernised cron schedule",
            f"# Original: {wf.source_file}",
            "",
            "schedules:",
        ]

        for step in wf.steps:
            lines.append(f"  - name: job_{step.step_number}")
            lines.append(f"    schedule: \"{step.target[:30]}\"")
            lines.append(f"    description: \"{step.description[:80]}\"")
            lines.append("")

        return WorkflowResult(
            original_workflow=wf,
            modern_file_path="schedules.yaml",
            modern_content="\n".join(lines) + "\n",
            workflow_type="schedule_config",
            description="Cron → YAML schedule",
        )

    def _convert_config(self, wf: DetectedWorkflow) -> WorkflowResult:
        """Convert config file to .env.example."""
        return WorkflowResult(
            original_workflow=wf,
            modern_file_path=".env.example",
            modern_content=(
                f"# Configuration from: {wf.source_file}\n"
                "# TODO: Extract key=value pairs from original config\n"
            ),
            workflow_type="env_file",
            description=f"Config → .env template",
        )

    def _convert_generic(self, wf: DetectedWorkflow) -> WorkflowResult:
        """Fallback converter for unknown workflow types."""
        return WorkflowResult(
            original_workflow=wf,
            modern_file_path=f"workflow_{wf.name}.md",
            modern_content=(
                f"# Workflow: {wf.name}\n\n"
                f"Original file: {wf.source_file}\n"
                f"Type: {wf.workflow_type}\n"
                f"Description: {wf.description}\n"
            ),
            workflow_type="documentation",
            description=f"Unknown workflow type documented",
        )
