import os
import ast
import logging
import time
from typing import List, Dict, Any, Optional, Union
from pathlib import Path

from scaledown.optimizer.base import BaseOptimizer
from scaledown.types import OptimizedContext
from scaledown.types.metrics import OptimizerMetrics, count_tokens
from scaledown.exceptions import OptimizerError

logger = logging.getLogger(__name__)

class SemanticOptimizer(BaseOptimizer):
    """
    An optimizer that uses local embeddings and FAISS to find semantically 
    relevant code chunks (functions/classes) for a given query.
    """

    def __init__(self, model_name: str = "Qwen/Qwen3-Embedding-0.6B", top_k: int = 3, target_model: str = "gpt-4o", **kwargs):
        super().__init__(target_model=target_model, **kwargs)
        self.model_name = model_name
        self.top_k = top_k
        self._model = None
        self._faiss = None
        self._numpy = None
        self.model_load_failed = False

    def _lazy_load_deps(self):
        """Lazily import heavy ML dependencies."""
        if self._model is not None or self.model_load_failed:
            return

        try:
            from sentence_transformers import SentenceTransformer
            import faiss
            import numpy as np
        except ImportError as e:
            raise OptimizerError(
                "SemanticOptimizer requires 'sentence-transformers', 'faiss-cpu', and 'numpy'. "
                "Install them with: pip install scaledown[semantic]"
            ) from e

        logger.info(f"Loading embedding model: {self.model_name}...")
        try:
            self._model = SentenceTransformer(self.model_name)
            self._faiss = faiss
            self._numpy = np
        except Exception as e:
            # Catch any error during model loading (Network, File missing, etc.)
            logger.error(f"Failed to load semantic model: {e}")
            logger.warning("Falling back to pass-through mode.")
            self.model_load_failed = True

    def _extract_semantic_units(self, file_path: str) -> List[Dict[str, Any]]:
        """Extracts functions and classes using AST."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                source = f.read()
            
            tree = ast.parse(source)
            units = []

            # Add the full file context
            units.append({
                "type": "file",
                "name": os.path.basename(file_path),
                "code": source,
                "metadata": {"file_name": os.path.basename(file_path)}
            })

            # Walk AST for Classes and Functions
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    units.append({
                        "type": "class",
                        "name": node.name,
                        "code": ast.get_source_segment(source, node),
                        "metadata": {"file_name": os.path.basename(file_path)}
                    })
                elif isinstance(node, ast.FunctionDef):
                    units.append({
                        "type": "function",
                        "name": node.name,
                        "code": ast.get_source_segment(source, node),
                        "metadata": {"file_name": os.path.basename(file_path)}
                    })
            return units
        except Exception as e:
            raise OptimizerError(f"Failed to parse AST for {file_path}: {e}")

    def optimize(
        self,
        context: Union[str, List[str]],
        query: Optional[str] = None,
        file_path: Optional[str] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> OptimizedContext:
        """
        Embeds the code in `file_path` and returns the segments most relevant to `query`.
        """
        start_time = time.time()

        if not file_path:
            logger.warning("SemanticOptimizer requires 'file_path'. Returning original.")
            orig_tokens = count_tokens(str(context), model=self.target_model)
            return self._create_fallback_context(str(context), orig_tokens, start_time, "missing_filepath")

        self._lazy_load_deps()
        
        # Extract Chunks
        units = self._extract_semantic_units(file_path)
        full_source = units[0]["code"] if units and units[0]["type"] == "file" else ""
        orig_tokens = count_tokens(full_source, model=self.target_model)

        # whether model fails to load
        if self.model_load_failed:
            return self._create_fallback_context(full_source, orig_tokens, start_time, "model_load_failed")
        
        if not units:
             return self._create_fallback_context("", orig_tokens, start_time, "no_units")

        # Embed Chunks
        valid_units = [u for u in units if u.get("code") and u.get("type") != "file"]
        
        if not valid_units:
             return self._create_fallback_context("", orig_tokens, start_time, "no_valid_chunks")

        codes = [u["code"] for u in valid_units]
        embeddings = self._model.encode(codes)

        # Build Index
        d = embeddings.shape[1]
        index = self._faiss.IndexFlatL2(d)
        index.add(self._numpy.array(embeddings, dtype=self._numpy.float32))

        # Embed Query & Search
        if not query:
             query = "main logic"

        query_emb = self._model.encode([query])
        k_search = min(self.top_k, len(valid_units))
        
        distances, indices = index.search(
            self._numpy.array(query_emb, dtype=self._numpy.float32), 
            k=k_search
        )

        # Construct Result
        results = []
        for idx in indices[0]:
            if idx != -1:
                results.append(valid_units[idx]["code"])

        final_content = "\n\n# ... [Semantic Context Search Result] ...\n\n".join(results)
        
        # Metrics Calculation
        opt_tokens = count_tokens(final_content, model=self.target_model)
        latency = (time.time() - start_time) * 1000
        ratio = opt_tokens / orig_tokens if orig_tokens > 0 else 0.0

        return OptimizedContext(
            content=final_content,
            metrics=OptimizerMetrics(
                original_tokens=orig_tokens,
                optimized_tokens=opt_tokens,
                chunks_retrieved=len(results),     
                compression_ratio=ratio,           
                latency_ms=latency,                
                retrieval_mode="semantic_search",  
                ast_fidelity=1.0
            )
        )

    def _create_fallback_context(self, content, tokens, start_time, reason):
        """Helper to create consistent fallback response."""
        return OptimizedContext(
            content=content,
            metrics=OptimizerMetrics(
                original_tokens=tokens,
                optimized_tokens=tokens,
                chunks_retrieved=0,
                compression_ratio=1.0,
                latency_ms=(time.time() - start_time) * 1000,
                retrieval_mode=f"fallback_{reason}",
                ast_fidelity=1.0
            )
        )
