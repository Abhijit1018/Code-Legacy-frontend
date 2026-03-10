import os
from typing import Optional

# Global configuration state
_API_KEY: Optional[str] = os.environ.get("SCALEDOWN_API_KEY")

def set_api_key(api_key: Optional[str]) -> None:
    """Sets the global API key for ScaleDown."""
    global _API_KEY
    _API_KEY = api_key

def get_api_key() -> Optional[str] :
    """Retrieves the global API key."""
    return _API_KEY
