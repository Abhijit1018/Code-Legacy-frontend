from dataclasses import dataclass, field
from typing import List, Dict, Any

@dataclass
class StepMetadata:
    """Captures metrics for a single step in the pipeline."""
    step_name: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def compression_ratio(self) -> float:
        if self.output_tokens <= 0: return 1.0
        return self.input_tokens / self.output_tokens

@dataclass
class PipelineResult:
    """Final output of the pipeline with full history."""
    final_content: str
    original_content: str
    history: List[StepMetadata] = field(default_factory=list)

    @property
    def original_tokens(self) -> int:
        return self.history[0].input_tokens if self.history else 0

    @property
    def final_tokens(self) -> int:
        return self.history[-1].output_tokens if self.history else 0

    @property
    def total_compression_ratio(self) -> float:
        if self.final_tokens == 0: return 0.0
        return self.original_tokens / self.final_tokens

    @property
    def savings_percent(self) -> float:
        if self.original_tokens == 0: return 0.0
        return (1 - (self.final_tokens / self.original_tokens)) * 100
