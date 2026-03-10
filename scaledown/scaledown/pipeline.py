from typing import List, Tuple, Union, Optional
from scaledown.optimizer.base import BaseOptimizer
from scaledown.compressor.base import BaseCompressor
from scaledown.types import OptimizedContext, CompressedPrompt
from scaledown.types import PipelineResult, StepMetadata
from scaledown.types.metrics import count_tokens

class Pipeline:
    """
    Pipeline for chaining optimizers and compressors.
    
    Example
    -------
    >>> from scaledown.pipeline import Pipeline
    >>> from scaledown.optimizer import HasteOptimizer
    >>> from scaledown.compressor import ScaleDownCompressor
    >>> 
    >>> pipe = Pipeline([
    ...     ('haste', HasteOptimizer()),
    ...     ('compressor', ScaleDownCompressor(model="gpt-4o"))
    ... ])
    >>> 
    >>> result = pipe.run(context=code, query="Add type hints", prompt="Explain changes")
    """
    
    def __init__(self, steps: List[Tuple[str, Union[BaseOptimizer, BaseCompressor]]]):
        """
        Initialize pipeline with ordered steps.
        
        Parameters
        ----------
        steps : List[Tuple[str, Union[BaseOptimizer, BaseCompressor]]]
            List of (name, transformer) tuples
        """
        self.steps = steps
        self._validate_steps()
    
    def _validate_steps(self):
        """Validate pipeline structure."""
        if not self.steps:
            raise ValueError("Pipeline must have at least one step")
        
        # Check that optimizers come before compressors
        seen_compressor = False
        for name, step in self.steps:
            if isinstance(step, BaseCompressor):
                seen_compressor = True
            elif isinstance(step, BaseOptimizer) and seen_compressor:
                raise ValueError(
                    f"Optimizer '{name}' cannot come after a compressor. "
                    "Pipeline order must be: optimizers -> compressors"
                )
    def run(self, context: str, **kwargs) -> PipelineResult:
        current_context = context
        original_context = context
        history: List[StepMetadata] = []

        for name, component in self.steps:
            step_type = "custom"
            inp, out, lat = 0, 0, 0.0
            
            # OPTIMIZER
            if isinstance(component, BaseOptimizer):
                step_type = "optimization"
                result = component.optimize(
                    context=current_context,
                    **kwargs
                )
                inp = getattr(result.metrics, 'original_tokens', 0)
                out = getattr(result.metrics, 'optimized_tokens', 0)
                lat = getattr(result.metrics, 'latency_ms', 0.0)
                current_context = result.content
            
            # COMPRESSOR
            elif isinstance(component, BaseCompressor):
                step_type = "compression"
                result = component.compress(
                    context=current_context,
                    **kwargs
                )
                inp = result.tokens[0]
                out = result.tokens[1]
                lat = result.latency
                current_context = result.content
            
            # UNKNOWN
            else:
                output = component(current_context, **kwargs)
                inp = count_tokens(current_context)
                out = count_tokens(output)
                current_context = output
            
            history.append(StepMetadata(
                step_name=name,
                input_tokens=inp,
                output_tokens=out,
                latency_ms=lat,
                details={"type": step_type, "component": component.__class__.__name__}
            ))

        return PipelineResult(
            final_content=current_context,
            original_content=original_context,
            history=history
        )
    
    def get_step(self, name: str) -> Union[BaseOptimizer, BaseCompressor]:
        """Get a step by name."""
        for step_name, step in self.steps:
            if step_name == name:
                return step
        raise KeyError(f"Step '{name}' not found in pipeline")
    
    def __repr__(self) -> str:
        step_names = [name for name, _ in self.steps]
        return f"Pipeline(steps={step_names})"


def make_pipeline(steps) -> Pipeline:
    """
    Helper function to create a pipeline.
    
    Parameters
    ----------
    *steps : tuples
        Variable number of (name, transformer) tuples
        
    Returns
    -------
    Pipeline
        Configured pipeline
        
    Example
    -------
    >>> pipe = make_pipeline(
    ...     ('haste', HasteOptimizer()),
    ...     ('compress', ScaleDownCompressor())
    ... )
    """
    return Pipeline(steps)
