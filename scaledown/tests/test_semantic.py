import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock
import numpy as np

import scaledown as sd
from scaledown.types import OptimizedContext

try:
    from scaledown.optimizer import SemanticOptimizer
    from sentence_transformers import SentenceTransformer
    SEMANTIC_DEPS_AVAILABLE = True
except ImportError:
    SEMANTIC_DEPS_AVAILABLE = False


TEST_CODE = """
class DataProcessor:
    def __init__(self):
        self.data = []

    def load_data(self, source):
        # Loading logic
        return True

    def process_batch(self, batch):
        # Complex processing
        return [x * 2 for x in batch]

def helper_function():
    pass
"""

@pytest.fixture
def temp_python_file():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
        f.write(TEST_CODE)
    temp_path = f.name
    yield temp_path
    if os.path.exists(temp_path):
        os.unlink(temp_path)

@pytest.mark.skipif(not SEMANTIC_DEPS_AVAILABLE, reason="Semantic deps not installed")
def test_initialization():
    opt = SemanticOptimizer(top_k=5)
    assert opt.top_k == 5
    assert opt.model_name == "Qwen/Qwen3-Embedding-0.6B"

@pytest.mark.skipif(not SEMANTIC_DEPS_AVAILABLE, reason="Semantic deps not installed")
def test_semantic_search_flow(temp_python_file):
    """Test standard flow with mocked model to avoid huge downloads in tests."""
    
    with patch("sentence_transformers.SentenceTransformer") as MockModel:
        # Setup mock model
        mock_instance = MockModel.return_value

        def mock_encode(texts):
            return np.array([[0.1, 0.2] for _ in texts], dtype=np.float32)
            
        mock_instance.encode.side_effect = mock_encode

        opt = SemanticOptimizer(top_k=1)
        
        result = opt.optimize(
            context="", 
            file_path=temp_python_file,
            query="process data"
        )
        
        assert isinstance(result, OptimizedContext)
        # Should contain the processed result
        assert "def process_batch" in result.content or "def load_data" in result.content
        assert result.metrics.retrieval_mode == "semantic_search"

@pytest.mark.skipif(not SEMANTIC_DEPS_AVAILABLE, reason="Semantic deps not installed")
def test_fallback_on_model_failure(temp_python_file):
    """Test that optimizer falls back gracefully if model fails to load (e.g., Error 54)."""
    
    with patch("sentence_transformers.SentenceTransformer", side_effect=Exception("Connection reset")):
        opt = SemanticOptimizer()
        
        result = opt.optimize(
            context=TEST_CODE,
            file_path=temp_python_file,
            query="test"
        )
        
        # Should return full content instead of crashing
        assert "class DataProcessor" in result.content
        assert result.metrics.retrieval_mode == "fallback_model_load_failed"
        assert result.metrics.original_tokens > 0

def test_missing_file_path():
    """Test behavior when file_path is missing."""
    if not SEMANTIC_DEPS_AVAILABLE:
        pytest.skip("Deps missing")

    opt = SemanticOptimizer()
    result = opt.optimize(context="some context", file_path=None)
    
    assert result.content == "some context"
    assert result.metrics.retrieval_mode.startswith("fallback")
