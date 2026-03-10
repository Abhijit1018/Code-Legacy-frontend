"""
End-to-end integration test — exercises the /api/analyze-snippet endpoint
which runs: context build → Scaledown compress → OpenRouter LLM.
"""
import sys, os, json, requests

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

# Ensure .env is loaded
from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

BASE_URL = "http://localhost:8000"

# --- 1. Health check ---
print("1. Health check...")
r = requests.get(f"{BASE_URL}/health")
assert r.status_code == 200, f"Health check failed: {r.text}"
print(f"   OK: {r.json()}")

# --- 2. Analyze snippet (COBOL) ---
print("\n2. Analyze COBOL snippet via /api/analyze-snippet...")
cobol_code = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. HELLO-WORLD.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-NAME PIC A(20).
       01 WS-GREETING PIC A(50).
       PROCEDURE DIVISION.
       MAIN-PARA.
           MOVE "World" TO WS-NAME.
           PERFORM GREET-PARA.
           DISPLAY WS-GREETING.
           STOP RUN.
       GREET-PARA.
           STRING "Hello, " DELIMITED SIZE
                  WS-NAME DELIMITED SPACE
                  "!" DELIMITED SIZE
                  INTO WS-GREETING.
"""

payload = {
    "code": cobol_code,
    "language": "cobol",
    "target_language": "python"
}

try:
    r = requests.post(f"{BASE_URL}/api/analyze-snippet", json=payload, timeout=180)
    print(f"   HTTP Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"   Compression savings: {data['stats']['compression_savings_percent']}%")
        print(f"   LLM model used: {data['llm']['model_used']}")
        print(f"   Tokens used: {data['llm']['tokens_used']}")
        print(f"   Summary length: {len(data['results']['summary'])} chars")
        print(f"   Python code length: {len(data['results']['python_code'])} chars")
        print(f"   Go code length: {len(data['results']['go_code'])} chars")
        print(f"   Docs length: {len(data['results']['documentation'])} chars")
        
        if data['results']['summary']:
            print(f"\n   --- SUMMARY (first 200 chars) ---")
            print(f"   {data['results']['summary'][:200]}")
        
        print("\n   SUCCESS — end-to-end pipeline works!")
    else:
        print(f"   ERROR: {r.text[:500]}")
except requests.exceptions.Timeout:
    print("   TIMEOUT — the request took longer than 180s")
except Exception as e:
    print(f"   ERROR: {e}")
