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
    # Empty means "use whatever the chosen theme says". Setting it to a
    # hex colour overrides the theme's foreground for code text only.
    'code_color': '',
    'line_height': 1.6,
    'letter_spacing': 0.5,
    'theme': 'high-contrast',
    'focus_mode': 'gutter',
    'blur_intensity': 0.5,
    'contrast': 'normal',
    'tts_enabled': False,
    'tts_engine': 'pyttsx3',
    'tts_voice': '',
    'tts_rate': 0.9,
}

# Editor palettes. These are the single source of truth: the settings
# screen reads them from /api/themes and app.js builds the CodeMirror
# theme from this response, so the code colours can never drift away
# from the surrounding chrome.
# Every value below is checked against its background for WCAG 2.1 AA
# (4.5:1) by tests/test_contrast.py.
THEMES = {
    'high-contrast': {
        'name': 'High Contrast',
        'bg': '#0b0b0b',
        'fg': '#ffffff',
        'selection': '#4d4300',
        'cursor': '#ffd93d',
        'gutter_bg': '#161616',
        'gutter_fg': '#a8a8a8',
        'keyword': '#ff9a9a',
        'string': '#93e6a8',
        'comment': '#b4b4b4',
        'number': '#ffd93d',
        'function': '#93d4ff',
        'variable': '#ffffff',
        'operator': '#ff9a9a',
        'punctuation': '#e8e8e8'
    },
    'dark': {
        'name': 'Dark',
        'bg': '#17181c',
        'fg': '#e6e6e6',
        'selection': '#234a6b',
        'cursor': '#6bc1ff',
        'gutter_bg': '#1f2126',
        'gutter_fg': '#98a0a8',
        'keyword': '#8fc0f5',
        'string': '#b9d99f',
        'comment': '#93a18d',
        'number': '#e3c583',
        'function': '#8ad4e8',
        'variable': '#dde2e8',
        'operator': '#c2cad2',
        'punctuation': '#c8cfd6'
    },
    'pastel': {
        'name': 'Pastel',
        'bg': '#fbf6ec',
        'fg': '#453f3a',
        'selection': '#e3d2ab',
        'cursor': '#b07d2c',
        'gutter_bg': '#f2ecdf',
        'gutter_fg': '#6b6258',
        'keyword': '#9a4a12',
        'string': '#427a20',
        'comment': '#6f675c',
        'number': '#8a6412',
        'function': '#1f6a94',
        'variable': '#3a4a52',
        'operator': '#584f47',
        'punctuation': '#584f47'
    },
    'light': {
        'name': 'Light',
        'bg': '#fcfcfc',
        'fg': '#2b2b2b',
        'selection': '#bcd6f2',
        'cursor': '#0057b8',
        'gutter_bg': '#f2f2f2',
        'gutter_fg': '#565656',
        'keyword': '#7a1fa2',
        'string': '#1b6b2f',
        'comment': '#5c5c5c',
        'number': '#a03000',
        'function': '#0057b8',
        'variable': '#2b2b2b',
        'operator': '#3d3d3d',
        'punctuation': '#4a4a4a'
    }
}

# Reading fonts. This table is the single source of truth: the settings
# screen and app.js both read it from /api/fonts, so a font can never be
# listed in one place and missing from the other. That duplication is
# what let OpenDyslexic ship as an HTML page under a .otf name while
# every other layer still believed the font existed.
#
# `family` is a CSS font stack. The browser uses the first family that
# actually has the characters on screen, so a missing font degrades to
# a plain sans-serif rather than to the generic `cursive`, which is
# close to unreadable for source code.
#
# `files` lists the font files this app bundles, and is empty for fonts
# taken from the computer. Calibri and Arial belong to Microsoft and
# cannot be redistributed in an open-source project, so they are
# referenced rather than shipped, with a free and metric-compatible
# stand-in behind them (Carlito for Calibri, Liberation Sans for Arial).
# Those stand-ins are not bundled either: they are named so that a user
# who has them installed, or who has installed them once, gets a
# sensible result instead of a broken font.
FONTS = {
    'OpenDyslexic': {
        'name': 'OpenDyslexic',
        'family': '"OpenDyslexic3", "OpenDyslexic", sans-serif',
        'files': ['OpenDyslexic3-Regular.ttf', 'OpenDyslexic3-Bold.ttf'],
        'bundled': True,
        'note': 'Designed for readers with dyslexia.'
    },
    'Atkinson Hyperlegible': {
        'name': 'Atkinson Hyperlegible',
        'family': '"Atkinson Hyperlegible", sans-serif',
        'files': [
            'AtkinsonHyperlegible-Regular.ttf',
            'AtkinsonHyperlegible-Bold.ttf',
        ],
        'bundled': True,
        'note': 'Designed to be clear at small sizes and low contrast.'
    },
    'Lexend': {
        'name': 'Lexend',
        'family': '"Lexend", sans-serif',
        'files': ['Lexend-Variable.ttf'],
        'bundled': True,
        'note': 'Designed for easy reading.'
    },
    'Nunito': {
        'name': 'Nunito',
        'family': '"Nunito", sans-serif',
        'files': ['Nunito-Variable.ttf'],
        'bundled': True,
        'note': 'Rounded and open, which many readers find easier to track.'
    },
    'Almarai': {
        'name': 'Almarai (Arabic)',
        'family': '"Almarai", sans-serif',
        'files': ['Almarai-Regular.ttf', 'Almarai-Bold.ttf'],
        'bundled': True,
        'note': 'For Arabic text.'
    },
    'Calibri': {
        'name': 'Calibri',
        'family': '"Calibri", "Carlito", "Segoe UI", sans-serif',
        'files': [],
        'bundled': False,
        'note': 'From your computer. Carlito is used instead if Calibri is missing.'
    },
    'Arial': {
        'name': 'Arial',
        'family': '"Arial", "Liberation Sans", "Helvetica", sans-serif',
        'files': [],
        'bundled': False,
        'note': 'From your computer. Liberation Sans is used instead if Arial is missing.'
    },
    'Comic Sans MS': {
        'name': 'Comic Sans MS',
        'family': '"Comic Sans MS", "Comic Sans", sans-serif',
        'files': [],
        'bundled': False,
        'note': 'From your computer.'
    },
    'Courier New': {
        'name': 'Courier New',
        'family': '"Courier New", Courier, monospace',
        'files': [],
        'bundled': False,
        'note': 'From your computer.'
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
    'code_color': str,
    'line_height': (int, float),
    'letter_spacing': (int, float),
    'theme': str,
    'focus_mode': str,
    'blur_intensity': (int, float),
    'contrast': str,
    'tts_enabled': bool,
    'tts_engine': str,
    'tts_voice': str,
    'tts_rate': (int, float),
}

CONFIG_VALUES = {
    'font': set(FONTS.keys()),
    'theme': set(THEMES.keys()),
    'focus_mode': {'off', 'gutter', 'lines'},
    'contrast': {'normal', 'high'},
}

# Numeric settings are bounded so a bad value can never produce an
# unreadable screen. (minimum, maximum)
CONFIG_RANGES = {
    'font_size': (12, 28),
    'line_height': (1.0, 2.4),
    'letter_spacing': (-0.5, 4.0),
    'blur_intensity': (0.0, 1.0),
    'tts_rate': (0.5, 2.0),
}

# Voice names come from the operating system, so any string is allowed -
# but not an unbounded one, and never markup.
CONFIG_MAX_LENGTHS = {
    'tts_voice': 200,
    'tts_engine': 50,
}

# Settings that are colours. These are written straight into a style
# attribute, so anything other than a plain hex colour is rejected
# outright: that keeps out CSS injection (`red; background: url(...)`)
# as well as the empty, broken and "transparent" values that would
# quietly make the code unreadable. A hex colour is the one colour
# format that cannot carry a second declaration.
CONFIG_HEX_COLORS = {'code_color'}

# Only the 3- and 6-digit forms. The 4- and 8-digit forms (with alpha)
# are left out on purpose: alpha is how a colour silently becomes
# unreadable, so it is not offered.
HEX_COLOR_RE = re.compile(r'^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$')


def _describe(key, value):
    """Plain-English explanation of why a setting was rejected."""
    if key in CONFIG_HEX_COLORS:
        return (
            '{} must be a colour like #1a1a1a, or left empty to use the '
            'theme colour.'.format(key.replace('_', ' '))
        )
    if key in CONFIG_RANGES:
        low, high = CONFIG_RANGES[key]
        return '{} must be between {} and {}.'.format(
            key.replace('_', ' '), low, high)
    if key in CONFIG_MAX_LENGTHS:
        return '{} is too long.'.format(key.replace('_', ' '))
    if key in CONFIG_VALUES:
        return '{} must be one of: {}.'.format(
            key.replace('_', ' '), ', '.join(sorted(CONFIG_VALUES[key])))
    return '{} is not a setting we recognise.'.format(key.replace('_', ' '))


@main_bp.route('/api/config', methods=['GET', 'POST'])
def config_api():
    if request.method == 'GET':
        return jsonify(load_config())

    data = request.get_json(silent=True) or {}

    # Access code gate (web version)
    if not access_code_ok(data):
        return jsonify({'success': False, 'error': 'Access code required.', 'code_required': True}), 403

    # The access code is a gate, not a setting. Drop it before validating
    # and before saving, otherwise it is rejected as an unknown key and
    # would be written into config.json in plain text.
    data = {key: value for key, value in data.items() if key != 'access_code'}

    # Validate keys and types
    invalid = []
    for key, value in data.items():
        if key not in CONFIG_TYPES:
            invalid.append(_describe(key, value))
            continue
        # bool is a subclass of int in Python, so True would otherwise
        # pass every numeric check (True == 1) and be written into a
        # numeric setting, where the browser then reads it as NaN.
        if key == 'tts_enabled':
            if not isinstance(value, bool):
                invalid.append(_describe(key, value))
                continue
        elif isinstance(value, bool) or not isinstance(value, CONFIG_TYPES[key]):
            invalid.append(_describe(key, value))
            continue
        if key in CONFIG_VALUES and value not in CONFIG_VALUES[key]:
            invalid.append(_describe(key, value))
            continue
        if key in CONFIG_HEX_COLORS:
            # An empty value is meaningful rather than missing: it means
            # "use the theme's colour", which is exactly what the reset
            # button sends.
            if value and (not isinstance(value, str)
                          or not HEX_COLOR_RE.match(value)):
                invalid.append(_describe(key, value))
                continue
        if key in CONFIG_RANGES:
            low, high = CONFIG_RANGES[key]
            if not (low <= value <= high):
                invalid.append(_describe(key, value))
                continue
        if key in CONFIG_MAX_LENGTHS and isinstance(value, str) \
                and len(value) > CONFIG_MAX_LENGTHS[key]:
            invalid.append(_describe(key, value))
            continue

    if invalid:
        return jsonify({
            'success': False,
            'error': 'Could not save that setting. ' + ' '.join(invalid)
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


# Python's mimetypes has no entry for .ttf on Windows, so fonts were
# being served as application/octet-stream. Browsers tolerate that, but
# a font served with a real font/* type is the correct answer and avoids
# surprises in stricter clients and in the packaged .exe.
FONT_MIME_TYPES = {
    '.ttf': 'font/ttf',
    '.otf': 'font/otf',
    '.woff': 'font/woff',
    '.woff2': 'font/woff2',
}


@main_bp.route('/assets/fonts/<path:filename>')
def serve_font(filename):
    mimetype = FONT_MIME_TYPES.get(Path(filename).suffix.lower())
    return send_from_directory('assets/fonts', filename, mimetype=mimetype)


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