import os
from typing import Optional

# Configuration
from scaledown.config import set_api_key, get_api_key

# Core Components
from scaledown.pipeline import Pipeline, make_pipeline
# HasteOptimizer is optional, import from scaledown.optimizer if needed
from scaledown.compressor.scaledown_compressor import ScaleDownCompressor

# Types & Exceptions
from scaledown.types import (
    CompressedPrompt,
    OptimizedContext,
    PipelineResult,
    StepMetadata
)

from scaledown.exceptions import (
    ScaleDownError,
    AuthenticationError,
    APIError
)

# Initialize global state if env var exists
_API_KEY: Optional[str] = os.environ.get("SCALEDOWN_API_KEY")

__all__ = [
    "Pipeline",
    "make_pipeline",
    "ScaleDownCompressor",
    "set_api_key",
    "get_api_key",
    "PipelineResult",
    "StepMetadata",
    "CompressedPrompt",
    "OptimizedContext",
    "ScaleDownError",
    "AuthenticationError",
    "APIError"
]
