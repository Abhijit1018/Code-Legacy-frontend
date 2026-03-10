import os

default_haste_api = "https://api.scaledown.xyz/haste"

def get_haste_api_url():
    """Get HASTE API URL from environment or default."""
    return os.getenv("HASTE_API_URL", default_haste_api)