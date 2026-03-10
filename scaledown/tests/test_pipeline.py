import pytest
import tempfile
import os
from unittest.mock import patch, MagicMock
import scaledown as sd

try:
    from scaledown.optimizer import HasteOptimizer, SemanticOptimizer
    DEPS_AVAILABLE = True
except ImportError:
    DEPS_AVAILABLE = False

TEST_CODE = """
def database_connect():
    return "connected"

def logic_process(data):
    return data * 2

def ui_render():
    print("rendering")
"""

@pytest.fixture
def temp_python_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(TEST_CODE)
    path = f.name
    yield path
    if os.path.exists(path):
        os.unlink(path)

@pytest.fixture
def complex_pipeline():
    if not DEPS_AVAILABLE:
        return None
        
    haste = HasteOptimizer(semantic=False, top_k=5)
    
    # Mock semantic optimizer to avoid loading model in pipeline test
    semantic = SemanticOptimizer(top_k=2)
    # Patch the expensive method on the instance directly
    semantic.optimize = MagicMock(return_value=sd.types.OptimizedContext(
        content="def logic_process(data):\n    return data * 2",
        metrics=sd.types.metrics.OptimizerMetrics(
            original_tokens=50, optimized_tokens=20, chunks_retrieved=1,
            compression_ratio=0.4, latency_ms=10, retrieval_mode="mock", ast_fidelity=1.0
        )
    ))
    
    compressor = sd.ScaleDownCompressor(api_key="test_key")
    
    return sd.Pipeline([
        ("haste", haste),
        ("semantic", semantic),
        ("compressor", compressor),
    ])

@pytest.mark.skipif(not DEPS_AVAILABLE, reason="Optimizers not installed")
@patch("requests.post")
def test_multi_step_pipeline(mock_post, complex_pipeline, temp_python_file):
    """Test flow: Haste -> Semantic -> Compressor"""
    
    # Mock Compressor API response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": {
            "compressed_prompt": "def logic(d):return d*2",
            "original_prompt_tokens": 20,
            "compressed_prompt_tokens": 10
        },
        "latency_ms": 100,
        "model_used": "gpt-4o"
    }
    mock_post.return_value = mock_response

    result = complex_pipeline.run(
        context=TEST_CODE,
        query="logic",
        file_path=temp_python_file,
        prompt="minify"
    )

    assert isinstance(result, sd.PipelineResult)
    # Check final result match
    assert result.final_content == "def logic(d):return d*2"
    
    # Verify chain history
    assert len(result.history) == 3
    assert result.history[0].step_name == "haste"
    assert result.history[1].step_name == "semantic"
    assert result.history[2].step_name == "compressor"
    
    # Verify semantic step received input from haste (implicit check via flow) and passed output to compressor
