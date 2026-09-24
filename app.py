#!/usr/bin/env python3
"""
AccessibleIDE - Main entry point.

Desktop app: runs a local Flask server in a background thread and shows
the IDE in a native window (PyWebView / WebView2) - no browser needed.

Web deployment (Render) uses `wsgi:app` via gunicorn and never reaches
the `__main__` block below.
"""
import os
import sys
import runpy
import socket
import threading
import time
import urllib.request

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from accessible_ide import create_app

app = create_app()


def _port_in_use(port):
    """Return True if something is already listening on the port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('127.0.0.1', port))
            return False
        except OSError:
            return True


def _wait_for_server(url, timeout=15):
    """Block until the local server responds, or return False on timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url + '/health', timeout=1)
            return True
        except Exception:
            time.sleep(0.2)
    return False


def _start_server(port):
    """Run the Flask server (debug off, localhost only)."""
    debug = os.environ.get('FLASK_DEBUG', '0') == '1'
    app.run(host='127.0.0.1', port=port, debug=debug, use_reloader=False)


def _run_desktop(port):
    """Launch the native desktop window (PyWebView)."""
    import webview  # imported lazily so the web deployment needs no pywebview

    url = f'http://127.0.0.1:{port}'

    # If the IDE is already running, just show a window for it and exit.
    if _port_in_use(port):
        webview.create_window(
            'AccessibleIDE',
            url,
            width=1200,
            height=800,
            min_size=(800, 600),
        )
        webview.start()
        return

    # Start the server, wait until it is ready, then open the window.
    threading.Thread(target=_start_server, args=(port,), daemon=True).start()
    if not _wait_for_server(url):
        print('AccessibleIDE could not start its local server.')
        sys.exit(1)

    webview.create_window(
        'AccessibleIDE',
        url,
        width=1200,
        height=800,
        min_size=(800, 600),
    )
    webview.start()

    # Window closed -> stop the server and exit.
    os._exit(0)


if __name__ == '__main__':
    # Hidden mode used by the code runner inside the packaged exe.
    # The exe cannot call a separate python.exe, so it re-invokes itself
    # with --run-script to execute a temp file and exit.
    if len(sys.argv) >= 3 and sys.argv[1] == '--run-script':
        runpy.run_path(sys.argv[2], run_name='__main__')
        sys.exit(0)

    port = int(os.environ.get('PORT', 5000))
    _run_desktop(port)