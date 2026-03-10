"""Wait for the server to be ready, then open the browser."""
import sys
import time
import urllib.request
import webbrowser

port = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
url = f"http://localhost:{port}"

for _ in range(60):
    try:
        urllib.request.urlopen(f"{url}/docs", timeout=2)
        webbrowser.open(url)
        break
    except Exception:
        time.sleep(1)
