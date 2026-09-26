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

from . import i18n

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
    'locale': i18n.DEFAULT_LOCALE,
    # Empty means "use whatever the chosen theme says". Setting it to a
    # hex colour overrides the theme's foreground for code text only.
    'code_color': '',
    'line_height': 1.6,
    'letter_spacing': 0.5,
    'theme': 'high-contrast',
    'focus_mode': 'gutter',
    'blur_intensity': 0.5,
    'contrast': 'normal',
    # None means "the reader has not chosen yet", so the app follows the
    # operating system's motion preference until they say otherwise. True
    # or False is a deliberate choice and is then the only thing honoured -
    # otherwise a reader who has asked for reduced motion at the OS level
    # could never turn movement back on here.
    'reduce_motion': None,
    'tts_enabled': False,
    'tts_engine': 'pyttsx3',
    'tts_voice': '',
    'tts_rate': 0.9,
    # How much of the screen a hover announces: nothing, only the things
    # that do something, or the words on the page as well. Default is the
    # middle one, because a screen reader's own choice matters more.
    'tts_hover_scope': 'controls',
    # Hovering pauses here before speaking, so that passing the pointer
    # across a row of buttons does not start a queue of voices.
    'tts_hover_delay': 600,
    'tts_click_to_speak': True,
    # The speech API does not say whether a voice is male or female, so
    # this is a preference applied to what is installed, not a promise.
    'tts_voice_gender': 'male',
    # On by default, because a reader who never hears about a fix has no way
    # to know it exists. Switching it off turns off the automatic check
    # only: a check the reader asked for still happens, because refusing to
    # answer a direct question is the same as being broken.
    'auto_update': True,
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
# Script fallbacks appended to every stack.
#
# None of the reading fonts carry Devanagari or Arabic, so without these a
# Hindi or Arabic reader gets empty boxes no matter which font they picked.
# The browser walks a font stack per character, which is what makes this
# work in the reader's favour: Latin still renders in the font they chose,
# Devanagari falls to Mukta and Arabic to Almarai, within the same line.
# Mukta comes first because it has no Arabic; Almarai comes first in
# Arabic only because nothing else in the stack has any.
SCRIPT_FALLBACKS = ('"Mukta"', '"Almarai"')


def _stack(*families, generic='sans-serif'):
    """Build a CSS font stack that can always render the shipped languages."""
    return ', '.join(list(families) + list(SCRIPT_FALLBACKS) + [generic])


FONTS = {
    'OpenDyslexic': {
        'name': 'OpenDyslexic',
        'family': _stack('"OpenDyslexic3"', '"OpenDyslexic"'),
        'files': ['OpenDyslexic3-Regular.ttf', 'OpenDyslexic3-Bold.ttf'],
        'bundled': True,
        'note': 'Designed for readers with dyslexia.'
    },
    'Atkinson Hyperlegible': {
        'name': 'Atkinson Hyperlegible',
        'family': _stack('"Atkinson Hyperlegible"'),
        'files': [
            'AtkinsonHyperlegible-Regular.ttf',
            'AtkinsonHyperlegible-Bold.ttf',
        ],
        'bundled': True,
        'note': 'Designed to be clear at small sizes and low contrast.'
    },
    'Lexend': {
        'name': 'Lexend',
        'family': _stack('"Lexend"'),
        'files': ['Lexend-Variable.ttf'],
        'bundled': True,
        'note': 'Designed for easy reading.'
    },
    'Nunito': {
        'name': 'Nunito',
        'family': _stack('"Nunito"'),
        'files': ['Nunito-Variable.ttf'],
        'bundled': True,
        'note': 'Rounded and open, which many readers find easier to track.'
    },
    'Calibri': {
        'name': 'Calibri',
        'family': _stack('"Calibri"', '"Carlito"', '"Segoe UI"'),
        'files': [],
        'bundled': False,
        'note': 'From your computer. Carlito is used instead if Calibri is missing.'
    },
    'Arial': {
        'name': 'Arial',
        'family': _stack('"Arial"', '"Liberation Sans"', '"Helvetica"'),
        'files': [],
        'bundled': False,
        'note': 'From your computer. Liberation Sans is used instead if Arial is missing.'
    },
    'Comic Sans MS': {
        'name': 'Comic Sans MS',
        'family': _stack('"Comic Sans MS"', '"Comic Sans"'),
        'files': [],
        'bundled': False,
        'note': 'From your computer.'
    },
    'Courier New': {
        'name': 'Courier New',
        'family': _stack('"Courier New"', 'Courier', generic='monospace'),
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


def translator_for(locale):
    """A ``t()`` for a locale, falling back to English for anything unknown.

    Error text is built on the server, but the reader's language is chosen
    in the browser. The client sends its locale with each run so the message
    matches the language actually on screen right now, rather than whatever
    was last written to disk.
    """
    return i18n.make_translator(i18n.normalise(locale) or i18n.DEFAULT_LOCALE)


def request_locale(data):
    """Locale for a request: the one the client sent, else the saved one."""
    sent = i18n.normalise((data or {}).get('locale'))
    if sent:
        return sent
    return i18n.normalise(load_config().get('locale')) or i18n.DEFAULT_LOCALE


# Which sentence to show for each way an update can go wrong. The updater
# itself knows only the short code, so this is the single place a new kind of
# failure is given words in five languages.
UPDATE_ERROR_KEYS = {
    'network': 'update.error_network',
    'too_large': 'update.error_too_large',
    'bad_manifest': 'update.error_bad_manifest',
    'no_checksum': 'update.error_no_checksum',
    'download_failed': 'update.error_download_failed',
    'checksum_failed': 'update.error_checksum',
    'not_applicable': 'update.error_not_applicable',
    'missing_build': 'update.error_missing_build',
    'prepare_failed': 'update.error_prepare',
    'start_failed': 'update.error_start',
    'bad_version': 'update.error_bad_version',
    'bad_url': 'update.error_bad_url',
    'checked_recently': 'update.error_checked_recently',
    'unknown': 'update.error_unknown',
}


def save_config(config):
    """Save user configuration to JSON file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)


# The Python exception types we explain, in the order they are tried when
# reading a traceback. Each one needs a python.<Name> key in every
# catalogue; tests/test_error_translation.py checks that.
PYTHON_ERROR_KEYS = (
    'SyntaxError', 'IndentationError', 'NameError', 'TypeError', 'ValueError',
    'IndexError', 'KeyError', 'AttributeError', 'ImportError',
    'ModuleNotFoundError', 'ZeroDivisionError', 'FileNotFoundError',
    'PermissionError', 'RecursionError', 'MemoryError', 'KeyboardInterrupt',
    'EOFError',
)


def translate_error(error_output, t=None):
    """Turn a Python traceback into a sentence a learner can act on.

    Returns a tuple: (friendly_message, line_number_or_None).

    ``t`` is the reader's translator. It is optional so existing callers and
    tests still get the English wording.
    """
    say = t or i18n.make_translator(i18n.DEFAULT_LOCALE)

    # ''.split('\n') is [''], not [], so an empty traceback needs its own
    # check. Without it the reader saw a bare "Error: " and nothing else.
    lines = [line for line in error_output.strip().split('\n') if line.strip()]
    if not lines:
        return say('python.unknown'), None
    
    # Get the last line (actual error)
    last_line = lines[-1].strip()
    
    # Common error translations
    translations = {
        name: say(f'python.{name}') for name in PYTHON_ERROR_KEYS
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
                        friendly += say('python.line_hint', part.strip())
                        break
                break
        return friendly, line_number
    
    # Fallback: return last line simplified
    return say('python.fallback', last_line), None


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


def check_sandbox(code, t=None):
    """Return (ok, message) for the sandboxed web runner.

    ``t`` is the caller's translator. It is optional so existing tests and
    any other caller still get plain English.
    """
    say = t or i18n.make_translator(i18n.DEFAULT_LOCALE)

    if not SANDBOX:
        return True, None

    # Block dangerous imports
    for match in IMPORT_RE.finditer(code):
        module = match.group(1)
        top = module.split('.')[0]
        if top in BLOCKED_IMPORTS:
            return False, say('error.blocked_import', module)

    # Block dangerous builtins and patterns
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, code):
            return False, say('error.blocked_general')

    return True, None


@main_bp.route('/')
def index():
    config = load_config()
    locale = i18n.normalise(config.get('locale')) or i18n.DEFAULT_LOCALE
    return render_template('index.html',
                         config=config,
                         themes=THEMES,
                         fonts=FONTS,
                         locale=locale,
                         direction=i18n.direction(locale),
                         languages=i18n.available(),
                         catalogue=i18n.load_catalogue(locale),
                         t=i18n.make_translator(locale))


@main_bp.route('/api/run', methods=['POST'])
def run_code():
    data = request.get_json(silent=True) or {}
    code = data.get('code', '')
    t = translator_for(request_locale(data))

    # Access code gate (web version)
    if not access_code_ok(data):
        return jsonify({
            'output': '',
            'error': t('error.access_code_run'),
            'error_line': None,
            'code_required': True
        }), 403

    # Rate limit
    if rate_limited(client_ip()):
        return jsonify({
            'output': '',
            'error': t('error.too_many_requests'),
            'error_line': None
        }), 429

    if not code.strip():
        return jsonify({'output': '', 'error': t('error.no_code'), 'error_line': None})

    # Sandbox check (web version)
    ok, sandbox_message = check_sandbox(code, t)
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
            error, error_line = translate_error(error, t)
        
        return jsonify({'output': output, 'error': error, 'error_line': error_line})
    
    except subprocess.TimeoutExpired:
        return jsonify({'output': '', 'error': t('error.timeout'), 'error_line': None})
    except Exception as e:
        return jsonify({'output': '', 'error': t('python.fallback', str(e)), 'error_line': None})
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
    'locale': str,
    'line_height': (int, float),
    'letter_spacing': (int, float),
    'theme': str,
    'focus_mode': str,
    'blur_intensity': (int, float),
    'contrast': str,
    'reduce_motion': bool,
    'tts_enabled': bool,
    'tts_engine': str,
    'tts_voice': str,
    'tts_rate': (int, float),
    'tts_hover_scope': str,
    'tts_hover_delay': (int, float),
    'tts_click_to_speak': bool,
    'tts_voice_gender': str,
    'auto_update': bool,
}

CONFIG_VALUES = {
    'font': set(FONTS.keys()),
    'theme': set(THEMES.keys()),
    'focus_mode': {'off', 'gutter', 'lines'},
    'contrast': {'normal', 'high'},
    'locale': set(i18n.LANGUAGES),
    'tts_hover_scope': {'off', 'controls', 'all'},
    'tts_voice_gender': {'any', 'male', 'female'},
}

# Numeric settings are bounded so a bad value can never produce an
# unreadable screen. (minimum, maximum)
CONFIG_RANGES = {
    'font_size': (12, 28),
    'line_height': (1.0, 2.4),
    'letter_spacing': (-0.5, 4.0),
    'blur_intensity': (0.0, 1.0),
    'tts_rate': (0.5, 2.0),
    # Milliseconds. Zero is allowed: someone who moves the pointer
    # deliberately and slowly should not have to wait at all. The top is
    # generous enough to be a deliberate request, low enough that nobody
    # can end up waiting half a minute for a word.
    'tts_hover_delay': (0, 3000),
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


def _describe(key, value, t):
    """Plain explanation of why a setting was rejected.

    The setting is named by its visible label ("Code text colour") rather
    than its config key, so a reader is pointed at the control they used.
    """
    label = t(i18n.CONFIG_LABELS.get(key, key))
    if key in CONFIG_HEX_COLORS:
        return t('config.error_colour', label)
    if key in CONFIG_RANGES:
        low, high = CONFIG_RANGES[key]
        return t('config.error_range', label, low, high)
    if key in CONFIG_MAX_LENGTHS:
        return t('config.error_too_long', label)
    if key in CONFIG_VALUES:
        allowed = ', '.join(sorted(CONFIG_VALUES[key]))
        return t('config.error_one_of', label, allowed)
    # A setting we know, sent the wrong sort of value. Saying "not a setting
    # we recognise" here would send the reader looking for a missing control
    # that is sitting right in front of them.
    if CONFIG_TYPES.get(key) is bool:
        return t('config.error_on_off', label)
    if key in CONFIG_TYPES:
        return t('config.error_value', label)
    return t('config.error_unknown', label)


@main_bp.route('/api/config', methods=['GET', 'POST'])
def config_api():
    if request.method == 'GET':
        return jsonify(load_config())

    data = request.get_json(silent=True) or {}
    t = translator_for(request_locale(data))

    # Access code gate (web version)
    if not access_code_ok(data):
        return jsonify({'success': False, 'error': t('error.access_required'), 'code_required': True}), 403

    # The access code is a gate, not a setting. Drop it before validating
    # and before saving, otherwise it is rejected as an unknown key and
    # would be written into config.json in plain text.
    data = {key: value for key, value in data.items() if key != 'access_code'}

    # Validate keys and types
    invalid = []
    for key, value in data.items():
        if key not in CONFIG_TYPES:
            invalid.append(_describe(key, value, t))
            continue
        # bool is a subclass of int in Python, so True would otherwise
        # pass every numeric check (True == 1) and be written into a
        # numeric setting, where the browser then reads it as NaN. The
        # mirror problem is a real bool arriving for a numeric setting, so
        # this applies to every switch rather than one named key.
        if CONFIG_TYPES[key] is bool:
            if not isinstance(value, bool):
                invalid.append(_describe(key, value, t))
                continue
        elif isinstance(value, bool) or not isinstance(value, CONFIG_TYPES[key]):
            invalid.append(_describe(key, value, t))
            continue
        if key in CONFIG_VALUES and value not in CONFIG_VALUES[key]:
            invalid.append(_describe(key, value, t))
            continue
        if key in CONFIG_HEX_COLORS:
            # An empty value is meaningful rather than missing: it means
            # "use the theme's colour", which is exactly what the reset
            # button sends.
            if value and (not isinstance(value, str)
                          or not HEX_COLOR_RE.match(value)):
                invalid.append(_describe(key, value, t))
                continue
        if key in CONFIG_RANGES:
            low, high = CONFIG_RANGES[key]
            if not (low <= value <= high):
                invalid.append(_describe(key, value, t))
                continue
        if key in CONFIG_MAX_LENGTHS and isinstance(value, str) \
                and len(value) > CONFIG_MAX_LENGTHS[key]:
            invalid.append(_describe(key, value, t))
            continue

    if invalid:
        return jsonify({
            'success': False,
            'error': t('config.error_prefix') + ' ' + ' '.join(invalid)
        }), 400

    config = load_config()
    config.update(data)
    save_config(config)
    return jsonify({'success': True, 'config': config})


@main_bp.route('/api/version')
def version_api():
    """What version is running, and whether it can update itself at all."""
    from . import __version__, updater
    return jsonify({
        'version': __version__,
        'applicable': updater.is_frozen(),
    })


@main_bp.route('/api/update/check', methods=['POST'])
def update_check_api():
    """Look for a newer build.

    The decision about whether to check at all is made here rather than in the
    browser, so the "check automatically" setting cannot be sidestepped by a
    page that simply asks anyway. An explicit request is always answered:
    turning the automatic check off is not a reason to say nothing when
    someone has asked a question.
    """
    from . import updater
    data = request.get_json(silent=True) or {}
    t = translator_for(request_locale(data))
    if not access_code_ok(data):
        return jsonify({
            'success': False,
            'error': t('error.access_required'),
            'code_required': True,
        }), 403

    asked = bool(data.get('force'))
    if not asked and not load_config().get('auto_update', True):
        return jsonify({
            'success': True,
            'applicable': updater.is_frozen(),
            'current': updater.current_version(),
            'update_available': False,
            'automatic': False,
            'error': '',
        })

    result = updater.check(force=asked)
    result['success'] = True
    result['automatic'] = not asked
    # The updater raises English sentences; the reader is reading one of five
    # languages. The code is looked up in the catalogue so the sentence that
    # reaches the screen is in the reader's own words. The English text stays
    # in the field only when a code has no catalogue entry, which is a bug
    # worth seeing rather than a sentence worth showing.
    code = result.get('error_code') or ''
    if code:
        key = UPDATE_ERROR_KEYS.get(code, 'update.error_unknown')
        result['error_text'] = t(key)
    return jsonify(result)


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
        t = translator_for(request_locale(request.get_json(silent=True) or {}))
        return jsonify({'success': False, 'error': t('error.not_on_web')}), 403

    def _stop():
        time.sleep(0.3)  # let the response flush first
        os._exit(0)

    threading.Thread(target=_stop, daemon=True).start()
    return jsonify({'success': True})