"""TTS2MP3 Studio — Desktop launcher.

Starts the FastAPI server in a background thread and opens a native
macOS WebKit window via pywebview, rendering the same web UI used
by the browser-based app.
"""

import os
import sys
import socket
import signal
import threading
import time

# Ensure project root is on the path (for PyInstaller bundles)
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
    # In a .app bundle, executable is in Contents/MacOS/
    # _internal/ sits alongside it with all packages
    if os.path.isdir(os.path.join(BASE_DIR, '_internal')):
        sys.path.insert(0, os.path.join(BASE_DIR, '_internal'))
    os.chdir(BASE_DIR)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

os.environ.setdefault("TTS2MP3_BASE_DIR", BASE_DIR)


def find_free_port():
    """Find an available TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def start_server(port: int):
    """Run uvicorn in a background thread."""
    import uvicorn

    # Patch server config paths for frozen apps
    if getattr(sys, 'frozen', False):
        from server import config
        data_dir = os.path.join(os.path.expanduser("~"), ".tts2mp3")
        os.makedirs(data_dir, exist_ok=True)
        config.CACHE_DIR = os.path.join(data_dir, "cache")
        config.JOBS_DIR = os.path.join(config.CACHE_DIR, "jobs")
        config.FAVORITES_FILE = os.path.join(data_dir, "favorites.json")
        config.SETTINGS_FILE = os.path.join(data_dir, "settings.json")
        config.PRONUNCIATION_FILE = os.path.join(data_dir, "pronunciations.json")
        config.HISTORY_FILE = os.path.join(data_dir, "history.json")

    uvicorn.run(
        "server.app:app",
        host="127.0.0.1",
        port=port,
        log_level="warning",
        access_log=False,
    )


def wait_for_server(port: int, timeout: float = 30):
    """Poll until the server is accepting connections."""
    import urllib.request
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/system/status", timeout=2)
            return True
        except Exception:
            time.sleep(0.3)
    return False


def main():
    import webview

    port = find_free_port()
    url = f"http://127.0.0.1:{port}/app/"

    server_thread = threading.Thread(target=start_server, args=(port,), daemon=True)
    server_thread.start()

    if not wait_for_server(port):
        print("Server failed to start within 30 seconds", file=sys.stderr)
        sys.exit(1)

    window = webview.create_window(
        "TTS2MP3 Studio",
        url,
        width=1100,
        height=760,
        min_size=(800, 600),
        text_select=True,
    )
    webview.start()


if __name__ == "__main__":
    main()
