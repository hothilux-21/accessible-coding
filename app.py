#!/usr/bin/env python3
"""
AccessibleIDE - Main entry point.
Run with: python app.py
Build exe with: pyinstaller --onefile --windowed --add-data "src/accessible_ide/static;accessible_ide/static" --add-data "src/accessible_ide/templates;accessible_ide/templates" --add-data "src/accessible_ide/assets;accessible_ide/assets" app.py
"""
import os
import sys
import runpy
import socket
import threading
import webbrowser

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from accessible_ide import create_app

app = create_app()


def _open_browser(url):
    """Open the IDE in the default browser (best effort, never crashes)."""
    try:
        webbrowser.open(url)
    except Exception:
        pass


def _port_in_use(port):
    """Return True if something is already listening on the port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('127.0.0.1', port))
            return False
        except OSError:
            return True


if __name__ == '__main__':
    # Hidden mode used by the code runner inside the packaged exe.
    # The exe cannot call a separate python.exe, so it re-invokes itself
    # with --run-script to execute a temp file and exit.
    if len(sys.argv) >= 3 and sys.argv[1] == '--run-script':
        runpy.run_path(sys.argv[2], run_name='__main__')
        sys.exit(0)

    # Local / desktop app server.
    # Debug is OFF by default and the server binds to localhost only.
    port = int(os.environ.get('PORT', 5000))
    url = f'http://127.0.0.1:{port}'

    # If the IDE is already running, just bring up the browser and exit.
    if _port_in_use(port):
        _open_browser(url)
        sys.exit(0)

    # Start the server, then open the browser once it is ready.
    threading.Timer(1.0, lambda: _open_browser(url)).start()
    debug = os.environ.get('FLASK_DEBUG', '0') == '1'
    app.run(host='127.0.0.1', port=port, debug=debug)