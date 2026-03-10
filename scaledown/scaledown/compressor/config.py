import os
default_scaledown_api="https://api.scaledown.xyz"

def get_api_url():
    return os.getenv("SCALEDOWN_API_URL", default_scaledown_api)
