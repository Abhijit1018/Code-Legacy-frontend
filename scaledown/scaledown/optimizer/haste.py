"""
HASTE optimizer integration for scaledown.
Uses the local HasteContext library for code context retrieval.
"""
from typing import Union, List, Optional, Dict, Any
import time
import os
import tempfile

try:
    from haste import select_from_file
    HASTE_AVAILABLE = True
except ImportError:
    HASTE_AVAILABLE = False

from .base import BaseOptimizer
from ..exceptions import OptimizerError
from ..types import OptimizedContext, OptimizerMetrics
from ..types.metrics import count_tokens


class HasteOptimizer(BaseOptimizer):
    """
    HASTE (Hybrid AST-guided Selection with Token-bounded Extraction) optimizer.
    
    Uses local HASTE library with Tree-sitter parsing, BM25 + semantic search,
    and AST-aware chunking to extract relevant code context.
    
    Parameters
    ----------
    top_k : int, default=6
        Number of top functions/classes to retrieve
    prefilter : int, default=300
        Size of candidate pool before reranking
    bfs_depth : int, default=1
        BFS expansion depth over call graph
    max_add : int, default=12
        Maximum nodes added during BFS expansion
    semantic : bool, default=False
        Enable semantic reranking with OpenAI embeddings
    sem_model : str, default='text-embedding-3-small'
        OpenAI embedding model for semantic search
    hard_cap : int, default=1200
        Hard token cap for output
    soft_cap : int, default=1800
        Soft token cap for output
    """
    
    def __init__(
        self,
        top_k: int = 6,
        prefilter: int = 300,
        bfs_depth: int = 1,
        max_add: int = 12,
        semantic: bool = False,
        sem_model: str = 'text-embedding-3-small',
        hard_cap: int = 1200,
        soft_cap: int = 1800,
        target_model: str = "gpt-4o",
        **kwargs
    ):
        super().__init__(target_model=target_model, **kwargs)
        
        if not HASTE_AVAILABLE:
            raise ImportError(
                "HASTE is not installed. Install with: pip install HasteContext>=0.2.1"
            )
        
        self.top_k = top_k
        self.prefilter = prefilter
        self.bfs_depth = bfs_depth
        self.max_add = max_add
        self.semantic = semantic
        self.sem_model = sem_model
        self.hard_cap = hard_cap
        self.soft_cap = soft_cap
    
    def optimize(
        self,
        context: Union[str, List[str]],
        query: Optional[str]=None,
        max_tokens: Optional[int] = None,
        file_path: Optional[str] = None,
        **kwargs
    ) -> Union[OptimizedContext, List[OptimizedContext]]:
        """
        Optimize code context using local HASTE library.
        
        Parameters
        ----------
        context : str or List[str]
            Source code content (currently expects file path in file_path param)
        query : str
            Query to guide context retrieval (e.g., "find training loop")
        max_tokens : int, optional
            Maximum token budget (uses hard_cap if not specified)
        file_path : str, optional
            Path to Python file to analyze (required for HASTE)
        **kwargs : dict
            Additional HASTE parameters
            
        Returns
        -------
        OptimizedContext
            Optimized context with relevant code and metrics
        """
        start_time = time.time()
        if query is None:
            query = kwargs.get("query")
        if file_path is None:
            file_path = kwargs.get("file_path")
        if max_tokens is None:
            max_tokens = kwargs.get("max_tokens")

        if not query:
            raise ValueError("Query is required for HASTE optimization")

        # 3. Handle string input without file_path by creating a temp file
        temp_path = None
        if not file_path:
            # If context is a string, we can try to write it to a temp file
            if isinstance(context, str) and len(context.strip()) > 0:
                # Write to temp file
                with tempfile.NamedTemporaryFile(
                    mode='w',
                    suffix='.py',
                    delete=False,
                    encoding='utf-8'
                ) as f:
                    f.write(context)
                    temp_path = f.name
                file_path = temp_path
            else:
                 raise ValueError(
                    "file_path is required for HASTE optimization, or context must be a valid code string."
                )


        try:
            # Call HASTE's select_from_file function
            result = select_from_file(
                path=file_path,
                query=query,
                top_k=self.top_k,
                prefilter=self.prefilter,
                bfs_depth=self.bfs_depth,
                max_add=self.max_add,
                semantic=self.semantic,
                sem_model=self.sem_model,
                hard_cap=max_tokens or self.hard_cap,
                soft_cap=self.soft_cap,
            )
            
            latency_ms = int((time.time() - start_time) * 1000)
            
            # Extract optimized code
            optimized_content = result.get('code', '')
            nodes = result.get('nodes', [])
            
            # Estimate original tokens
            original_tokens = 0
            if file_path and os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    original_code = f.read()
                original_tokens = count_tokens(original_code, model=self.target_model)
            
            optimized_tokens = count_tokens(optimized_content, model=self.target_model)
            
            metrics = OptimizerMetrics(
                original_tokens=original_tokens,
                optimized_tokens=optimized_tokens,
                chunks_retrieved=len(nodes),
                compression_ratio=original_tokens / max(optimized_tokens, 1),
                latency_ms=latency_ms,
                retrieval_mode='hybrid' if self.semantic else 'bm25',
                ast_fidelity=1.0 
            )
            
            return OptimizedContext(
                content=optimized_content,
                metrics=metrics
            )
            
        except Exception as e:
            raise OptimizerError(f"HASTE optimization failed: {str(e)}")
        finally:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)
# Alias for backward compatibility
HasteContext = HasteOptimizer
    