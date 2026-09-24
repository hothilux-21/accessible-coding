"""
Main routes for AccessibleIDE.
"""
from flask import Blueprint, render_template, request, jsonify, send_from_directory
import subprocess
import sys
import json
import os
import re
import time
import tempfile
import signal
import threading
from pathlib import Path

main_bp = Blueprint('main', __name__)

# Access code for the web version. If set, /api/run and /api/config POST
# require it. If NOT set, the code runner is disabled (maintenance mode).
ACCESS_CODE = os.environ.get('ACCESS_CODE', '')

# Sandbox the code runner on the web. The desktop exe runs full Python.
SANDBOX = os.environ.get('SANDBOX', '0') == '1' or bool(os.environ.get('RENDER'))

# Simple in-memory rate limiting (per IP)
RATE_LIMIT = {}
RATE_MAX = 10          # requests per window
RATE_WINDOW = 60       # seconds

# Modules that are blocked in the sandboxed web runner
BLOCKED_IMPORTS = [
    'os', 'sys', 'subprocess', 'socket', 'requests', 'urllib', 'http',
    'ftplib', 'smtplib', 'telnetlib', 'poplib', 'imaplib', 'importlib',
    'ctypes', 'multiprocessing', 'threading', 'shutil', 'pathlib', 'glob',
    'tempfile', 'pickle', 'marshal', 'shelve', 'sqlite3', 'webbrowser',
    'platform', 'getpass', 'pwd', 'grp', 'resource', 'signal', 'asyncio',
    'concurrent', 'ssl', 'ftplib', 'nntplib', 'cgi', 'cgitb', 'wsgiref',
]

# Builtins that are blocked in the sandboxed web runner
BLOCKED_BUILTINS = [
    'open', 'eval', 'exec', 'compile', '__import__', 'input', 'breakpoint',
    'globals', 'locals', 'vars', 'getattr', 'setattr', 'delattr',
    'memoryview', 'help', 'exit', 'quit', 'copyright', 'credits', 'license',
]

# Patterns that are blocked in the sandboxed web runner
BLOCKED_PATTERNS = [
    r'__\w+__',          # dunder access (e.g. __import__, __builtins__)
    r'\bopen\s*\(', r'\beval\s*\(', r'\bexec\s*\(', r'\bcompile\s*\(',
    r'\binput\s*\(', r'\bbreakpoint\s*\(', r'\bglobals\s*\(', r'\blocals\s*\(',
    r'\bvars\s*\(', r'\bgetattr\s*\(', r'\bsetattr\s*\(', r'\bdelattr\s*\(',
]

IMPORT_RE = re.compile(r'^\s*(?:import|from)\s+([a-zA-Z_][a-zA-Z0-9_]*)', re.MULTILINE)

# Config file path
CONFIG_DIR = Path.home() / '.accessible-ide'
CONFIG_FILE = CONFIG_DIR / 'config.json'

DEFAULT_CONFIG = {
    'font': 'Atkinson Hyperlegible',
    'font_size': 16,
    'line_height': 1.6,
    'letter_spacing': 0.5,
    'theme': 'high-contrast',
    'focus_mode': 'gutter',
    'blur_intensity': 0.5,
    'tts_enabled': False,
    'tts_engine': 'pyttsx3'
}

THEMES = {
    'high-contrast': {
        'name': 'High Contrast',
        'bg': '#0d0d0d',
        'fg': '#ffffff',
        'selection': '#ffff00',
        'cursor': '#ffff00',
        'gutter_bg': '#1a1a1a',
        'gutter_fg': '#888888',
        'keyword': '#ff6b6b',
        'string': '#69db7c',
        'comment': '#888888',
        'number': '#ffd93d',
        'function': '#74b9ff',
        'variable': '#ffffff',
        'operator': '#ff6b6b',
        'punctuation': '#ffffff'
    },
    'dark': {
        'name': 'Dark',
        'bg': '#1e1e1e',
        'fg': '#d4d4d4',
        'selection': '#264f78',
        'cursor': '#ffffff',
        'gutter_bg': '#252526',
        'gutter_fg': '#858585',
        'keyword': '#569cd6',
        'string': '#ce9178',
        'comment': '#6a9955',
        'number': '#b5cea8',
        'function': '#dcdcaa',
        'variable': '#9cdcfe',
        'operator': '#d4d4d4',
        'punctuation': '#d4d4d4'
    },
    'pastel': {
        'name': 'Pastel',
        'bg': '#fdf6e3',
        'fg': '#586e75',
        'selection': '#eee8d5',
        'cursor': '#586e75',
        'gutter_bg': '#eee8d5',
        'gutter_fg': '#93a1a1',
        'keyword': '#cb4b16',
        'string': '#859900',
        'comment': '#93a1a1',
        'number': '#b58900',
        'function': '#268bd2',
        'variable': '#2aa198',
        'operator': '#586e75',
        'punctuation': '#586e75'
    },
    'light': {
        'name': 'Light',
        'bg': '#ffffff',
        'fg': '#333333',
        'selection': '#add6ff',
        'cursor': '#333333',
        'gutter_bg': '#f5f5f5',
        'gutter_fg': '#999999',
        'keyword': '#0000ff',
        'string': '#008000',
        'comment': '#808080',
        'number': '#ff0000',
        'function': '#800080',
        'variable': '#333333',
        'operator': '#333333',
        'punctuation': '#333333'
    }
}

FONTS = {
    'OpenDyslexic': {
        'name': 'OpenDyslexic',
        'family': '"OpenDyslexic3", "OpenDyslexic", cursive',
        'files': ['OpenDyslexic3-Regular.otf', 'OpenDyslexic3-Bold.otf']
    },
    'Atkinson Hyperlegible': {
        'name': 'Atkinson Hyperlegible',
        'family': '"Atkinson Hyperlegible", sans-serif',
        'files': ['AtkinsonHyperlegible-Regular.ttf', 'AtkinsonHyperlegible-Bold.ttf']
    },
    'Comic Sans MS': {
        'name': 'Comic Sans MS',
        'family': '"Comic Sans MS", cursive',
        'files': []
    },
    'Courier New': {
        'name': 'Courier New',
        'family': '"Courier New", monospace',
        'files': []
    }
}


def load_config():
    """Load user configuration from JSON file."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
            # Merge with defaults for any missing keys
            for key, value in DEFAULT_CONFIG.items():
                if key not in config:
                    config[key] = value
            return config
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()


def save_config(config):
    """Save user configuration to JSON file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)


def translate_error(error_output):
    """Convert Python traceback to plain English.

    Returns a tuple: (friendly_message, line_number_or_None).
    """
    lines = error_output.strip().split('\n')
    if not lines:
        return "An unknown error occurred.", None
    
    # Get the last line (actual error)
    last_line = lines[-1].strip()
    
    # Common error translations
    translations = {
        'SyntaxError': 'There\'s a syntax error in your code. Check for missing parentheses, brackets, or quotes.',
        'IndentationError': 'Indentation error. Python uses spaces to group code blocks. Make sure your indentation is consistent.',
        'NameError': 'You\'re using a variable or function name that hasn\'t been defined yet.',
        'TypeError': 'You\'re trying to do something with the wrong type of data (like adding text to a number).',
        'ValueError': 'A function received a value of the right type but an inappropriate value.',
        'IndexError': 'You\'re trying to access an index that doesn\'t exist in a list or string.',
        'KeyError': 'You\'re trying to access a dictionary key that doesn\'t exist.',
        'AttributeError': 'You\'re trying to use an attribute or method that doesn\'t exist on this object.',
        'ImportError': 'Python can\'t find the module you\'re trying to import.',
        'ModuleNotFoundError': 'The module you\'re trying to import isn\'t installed.',
        'ZeroDivisionError': 'You\'re dividing by zero, which isn\'t allowed.',
        'FileNotFoundError': 'The file you\'re trying to open doesn\'t exist.',
        'PermissionError': 'You don\'t have permission to access this file.',
        'RecursionError': 'Your function is calling itself too many times (infinite recursion).',
        'MemoryError': 'Your program ran out of memory.',
        'KeyboardInterrupt': 'The program was interrupted (Ctrl+C).',
        'EOFError': 'Unexpected end of input.',
    }
    
    # Extract error type
    error_type = None
    for et in translations:
        if et in last_line:
            error_type = et
            break
    
    if error_type:
        friendly = translations[error_type]
        # Add line number if available
        line_number = None
        for line in reversed(lines):
            if 'line' in line and '.py' in line:
                parts = line.split(',')
                for part in parts:
                    if 'line' in part:
                        # Extract the number (e.g. "line 12")
                        match = re.search(r'line\s+(\d+)', part)
                        if match:
                            line_number = int(match.group(1))
                        friendly += f' (around {part.strip()})'
                        break
                break
        return friendly, line_number
    
    # Fallback: return last line simplified
    return f"Error: {last_line}", None


def access_code_ok(data):
    """Check the access code, if one is configured.

    - No ACCESS_CODE set: open (the sandbox is the protection).
    - ACCESS_CODE set: code required.
    """
    if not ACCESS_CODE:
        return True
    return data.get('access_code', '') == ACCESS_CODE


def rate_limited(ip):
    """Return True if the IP has exceeded the request limit."""
    now = time.time()
    # Clean up old entries occasionally
    if len(RATE_LIMIT) > 1000:
        for key in list(RATE_LIMIT.keys()):
            RATE_LIMIT[key] = [t for t in RATE_LIMIT[key] if now - t < RATE_WINDOW]
            if not RATE_LIMIT[key]:
                del RATE_LIMIT[key]
    recent = [t for t in RATE_LIMIT.get(ip, []) if now - t < RATE_WINDOW]
    if len(recent) >= RATE_MAX:
        return True
    recent.append(now)
    RATE_LIMIT[ip] = recent
    return False


def client_ip():
    """Best-effort client IP (handles Render's proxy)."""
    forwarded = request.headers.get('X-Forwarded-For', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.remote_addr or 'unknown'


def check_sandbox(code):
    """Return (ok, message) for the sandboxed web runner."""
    if not SANDBOX:
        return True, None

    # Block dangerous imports
    for match in IMPORT_RE.finditer(code):
        module = match.group(1)
        top = module.split('.')[0]
        if top in BLOCKED_IMPORTS:
            return False, (
                'This code uses a feature that is not allowed in the web '
                'version (importing "{0}"). Try simpler code, or use the '
                'desktop app for full Python.'.format(module)
            )

    # Block dangerous builtins and patterns
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, code):
            return False, (
                'This code uses a feature that is not allowed in the web '
                'version. Try simpler code, or use the desktop app for full '
                'Python.'
            )

    return True, None


@main_bp.route('/')
def index():
    config = load_config()
    return render_template('index.html', 
                         config=config,
                         themes=THEMES,
                         fonts=FONTS)


@main_bp.route('/api/run', methods=['POST'])
def run_code():
    data = request.get_json(silent=True) or {}
    code = data.get('code', '')

    # Access code gate (web version)
    if not access_code_ok(data):
        return jsonify({
            'output': '',
            'error': 'This site is protected. Enter the access code to run code.',
            'error_line': None,
            'code_required': True
        }), 403

    # Rate limit
    if rate_limited(client_ip()):
        return jsonify({
            'output': '',
            'error': 'Too many requests. Please wait a moment and try again.',
            'error_line': None
        }), 429

    if not code.strip():
        return jsonify({'output': '', 'error': 'No code to run.', 'error_line': None})

    # Sandbox check (web version)
    ok, sandbox_message = check_sandbox(code)
    if not ok:
        return jsonify({'output': '', 'error': sandbox_message, 'error_line': None})

    # Write code to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(code)
        temp_file = f.name
    
    try:
        # Run with timeout.
        # In the packaged exe, sys.executable is the exe itself, so we
        # re-invoke it with --run-script to execute the temp file.
        if getattr(sys, 'frozen', False):
            cmd = [sys.executable, '--run-script', temp_file]
        else:
            cmd = [sys.executable, temp_file]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
            cwd=tempfile.gettempdir()
        )
        
        output = result.stdout
        error = result.stderr
        error_line = None
        
        if error:
            error, error_line = translate_error(error)
        
        return jsonify({'output': output, 'error': error, 'error_line': error_line})
    
    except subprocess.TimeoutExpired:
        return jsonify({'output': '', 'error': 'Code timed out (10 second limit). Check for infinite loops.', 'error_line': None})
    except Exception as e:
        return jsonify({'output': '', 'error': f'Execution error: {str(e)}', 'error_line': None})
    finally:
        # Clean up
        try:
            os.unlink(temp_file)
        except Exception:
            pass


# Allowed config keys and their expected types
CONFIG_TYPES = {
    'font': str,
    'font_size': int,
    'line_height': (int, float),
    'letter_spacing': (int, float),
    'theme': str,
    'focus_mode': str,
    'blur_intensity': (int, float),
    'tts_enabled': bool,
    'tts_engine': str,
}

CONFIG_VALUES = {
    'font': set(FONTS.keys()),
    'theme': set(THEMES.keys()),
    'focus_mode': {'off', 'gutter', 'lines'},
}


@main_bp.route('/api/config', methods=['GET', 'POST'])
def config_api():
    if request.method == 'GET':
        return jsonify(load_config())

    data = request.get_json(silent=True) or {}

    # Access code gate (web version)
    if not access_code_ok(data):
        return jsonify({'success': False, 'error': 'Access code required.', 'code_required': True}), 403

    # Validate keys and types
    invalid = []
    for key, value in data.items():
        if key not in CONFIG_TYPES:
            invalid.append(key)
            continue
        if not isinstance(value, CONFIG_TYPES[key]):
            invalid.append(key)
            continue
        if key in CONFIG_VALUES and value not in CONFIG_VALUES[key]:
            invalid.append(key)

    if invalid:
        return jsonify({
            'success': False,
            'error': 'Invalid settings: ' + ', '.join(invalid) + '.'
        }), 400

    config = load_config()
    config.update(data)
    save_config(config)
    return jsonify({'success': True, 'config': config})


@main_bp.route('/api/themes')
def themes_api():
    return jsonify(THEMES)


@main_bp.route('/api/fonts')
def fonts_api():
    return jsonify(FONTS)


@main_bp.route('/assets/fonts/<path:filename>')
def serve_font(filename):
    return send_from_directory('assets/fonts', filename)


@main_bp.route('/health')
def health():
    return jsonify({'status': 'ok'})


@main_bp.route('/api/shutdown', methods=['POST'])
def shutdown():
    """Stop the desktop app server. Local-only: never exposed on the web."""
    if os.environ.get('RENDER'):
        return jsonify({'success': False, 'error': 'Not available on the web.'}), 403

    def _stop():
        time.sleep(0.3)  # let the response flush first
        os._exit(0)

    threading.Thread(target=_stop, daemon=True).start()
    return jsonify({'success': True})