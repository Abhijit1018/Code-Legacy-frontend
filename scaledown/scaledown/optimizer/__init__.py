from typing import TYPE_CHECKING

from .base import BaseOptimizer

# Define what to expose
__all__ = ["BaseOptimizer", "HasteOptimizer", "SemanticOptimizer"]

def __getattr__(name):
    if name == "HasteOptimizer":
        try:
            from .haste import HasteOptimizer
            return HasteOptimizer
        except ImportError as e:
            raise ImportError(
                "HasteOptimizer requires 'haste'. Install with `pip install scaledown[haste]`"
            ) from e
            
    if name == "SemanticOptimizer":
        try:
            from .semantic_code import SemanticOptimizer
            return SemanticOptimizer
        except ImportError as e:
            raise ImportError(
                "SemanticOptimizer requires 'semantic'. Install with `pip install scaledown[semantic]`"
            ) from e
            
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

if TYPE_CHECKING:
    from .haste import HasteOptimizer
    from .semantic_code import SemanticOptimizer
