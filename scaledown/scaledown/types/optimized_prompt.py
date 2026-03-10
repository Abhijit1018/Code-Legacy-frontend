from dataclasses import dataclass
from .metrics import OptimizerMetrics

@dataclass
class OptimizedContext:
    content: str
    metrics: OptimizerMetrics

    @property
    def compression_ratio(self) -> float:
        return self.metrics.compression_ratio
