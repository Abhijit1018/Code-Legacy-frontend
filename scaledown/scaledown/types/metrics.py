from dataclasses import dataclass
import logging
logger = logging.getLogger(__name__)
try:
    import tiktoken

except ImportError:
    tiktoken = None

def count_tokens(text: str, model: str = "gpt-4o") -> int:
    """
    Count tokens using tiktoken. 
    
    If the provided model is not compatible with tiktoken (e.g., Claude, Llama),
    it falls back to 'cl100k_base' (GPT-4) encoding to ensure a standard metric.
    """
    if not text:
        return 0
        
    if tiktoken is None:
        raise ImportError(
            "tiktoken is required for accurate metrics. "
            "Install it with: pip install tiktoken"
        )
            
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        # Fallback for non-OpenAI models to a standard encoding
        logger.debug(f"Model '{model}' not found in tiktoken. Defaulting to cl100k_base.")
        encoding = tiktoken.get_encoding("cl100k_base")
        
    return len(encoding.encode(text))

@dataclass
class OptimizerMetrics:
    original_tokens: int
    optimized_tokens: int
    chunks_retrieved: int
    compression_ratio: float
    latency_ms: float
    retrieval_mode: str
    ast_fidelity: float

@dataclass
class CompressorMetrics:
    original_tokens: int
    compressed_tokens: int
    compression_ratio: float
    latency_ms: float
    model_used: str
    cost_saved: float
