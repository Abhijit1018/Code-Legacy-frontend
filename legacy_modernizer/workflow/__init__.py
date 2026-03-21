"""Workflow sub-package — detect legacy workflows and convert to modern equivalents."""

from .detector import WorkflowDetector, DetectedWorkflow
from .converter import WorkflowConverter, WorkflowResult
from .structure_generator import StructureGenerator

__all__ = [
    "WorkflowDetector",
    "WorkflowConverter",
    "WorkflowResult",
    "DetectedWorkflow",
    "StructureGenerator",
]
