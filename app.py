#!/usr/bin/env python3
"""
AccessibleIDE - Main entry point.
Run with: python app.py
Build exe with: pyinstaller --onefile --windowed --add-data "src/accessible_ide/static;accessible_ide/static" --add-data "src/accessible_ide/templates;accessible_ide/templates" --add-data "src/accessible_ide/assets;accessible_ide/assets" app.py
"""
import os
import sys
import runpy

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from accessible_ide import create_app

app = create_app()

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
    debug = os.environ.get('FLASK_DEBUG', '0') == '1'
    app.run(host='127.0.0.1', port=port, debug=debug)