class ScaleDownError(Exception):
    """Base exception for ScaleDown errors."""
    pass

class AuthenticationError(ScaleDownError):
    """Raised when API key is missing or invalid."""
    pass

class APIError(ScaleDownError):
    """Raised when the ScaleDown API returns an error."""
    pass

class OptimizerError(ScaleDownError):
    """Raised when an optimizer encounters an error."""
    pass

class PipelineError(ScaleDownError):
    """Raised when pipeline execution fails."""
    pass