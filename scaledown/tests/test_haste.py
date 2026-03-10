import os
import tempfile
import pytest
import scaledown as sd
from scaledown.types import OptimizedContext

try:
    from scaledown.optimizer import HasteOptimizer
except ImportError:
    pytest.skip("HasteOptimizer not available.", allow_module_level=True)

TEST_CODE = """
def dependency(x):
    return x + 1

def target_function(x):
    return dependency(x) * 2

class UnusedClass:
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

def test_initialization():
    opt = HasteOptimizer(top_k=5, target_model="gpt-3.5-turbo")
    assert opt.top_k == 5
    assert opt.target_model == "gpt-3.5-turbo"

def test_optimization_with_file(temp_python_file):
    opt = HasteOptimizer(top_k=2, semantic=False)
    result = opt.optimize(
        context="", 
        query="target_function", 
        file_path=temp_python_file
    )
    
    assert isinstance(result, OptimizedContext)
    # Should find the target function
    assert "def target_function" in result.content
    # Metrics should be populated
    assert result.metrics.original_tokens > 0
