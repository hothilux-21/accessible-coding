"""Smoke test for AccessibleIDE (includes security checks)."""
import sys
import os
import io
import pathlib
import tempfile

# Enable the sandbox for tests (same as the web deployment)
os.environ['SANDBOX'] = '1'

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from accessible_ide import create_app

# Several checks below assert on the wording of an error sentence. Sending a
# locale with every request keeps them about the English text rather than
# about whatever language the machine happens to have saved, and the
# temporary config stops the run from overwriting the reader's real
# settings - which it used to do.
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import accessible_ide.routes as routes

_tmp = tempfile.TemporaryDirectory()
routes.CONFIG_DIR = pathlib.Path(_tmp.name)
routes.CONFIG_FILE = routes.CONFIG_DIR / 'config.json'
routes.ACCESS_CODE = ''

app = create_app()
c = app.test_client()


def run(code, **extra):
    """POST /api/run in English, whatever is saved on this machine."""
    return c.post('/api/run', json={'code': code, 'locale': 'en', **extra})


def settings(**payload):
    return c.post('/api/config', json={'locale': 'en', **payload})

# Test index page
r = c.get('/')
print('GET / ->', r.status_code, '(len:', len(r.data), ')')
assert r.status_code == 200

# Test run code (success)
r2 = c.post('/api/run', json={'code': 'print("hello")'})
print('POST /api/run ->', r2.status_code, r2.get_json())
assert r2.status_code == 200 and 'hello' in r2.get_json()['output']

# Test run code (error)
r3 = c.post('/api/run', json={'code': 'x = 1/0'})
print('POST /api/run (error) ->', r3.get_json())
assert r3.get_json().get('error_line') is not None, 'error_line missing for runtime error'

# Test run code (syntax error)
r4 = c.post('/api/run', json={'code': 'def foo(:\n    pass'})
print('POST /api/run (syntax) ->', r4.get_json())
assert r4.get_json().get('error_line') is not None, 'error_line missing for syntax error'

# --- Security checks ---

# Sandbox: dangerous import blocked
r5 = c.post('/api/run', json={'code': 'import os\nos.system("echo hi")'})
print('POST /api/run (blocked import) ->', r5.get_json())
assert 'not allowed' in r5.get_json()['error'], 'dangerous import not blocked'

# Sandbox: dangerous builtin blocked
r6 = c.post('/api/run', json={'code': 'print(open("secret.txt").read())'})
print('POST /api/run (blocked builtin) ->', r6.get_json())
assert 'not allowed' in r6.get_json()['error'], 'open() not blocked'

# Sandbox: dunder access blocked
r7 = c.post('/api/run', json={'code': 'print(__import__("os"))'})
print('POST /api/run (blocked dunder) ->', r7.get_json())
assert 'not allowed' in r7.get_json()['error'], 'dunder access not blocked'

# Sandbox: safe imports still work
r8 = c.post('/api/run', json={'code': 'import math\nprint(math.pi)'})
print('POST /api/run (safe import) ->', r8.get_json())
assert '3.14' in r8.get_json()['output'], 'safe import blocked'

# Config: invalid key rejected
r9 = settings(evil_key='x')
print('POST /api/config (bad key) ->', r9.status_code, r9.get_json())
assert r9.status_code == 400, 'invalid config key accepted'

# Config: invalid value rejected
r10 = settings(font_size='huge')
print('POST /api/config (bad type) ->', r10.status_code, r10.get_json())
assert r10.status_code == 400, 'invalid config type accepted'

# Config: valid update accepted
r11 = settings(font='OpenDyslexic')
print('POST /api/config (valid) ->', r11.status_code, r11.get_json())
assert r11.status_code == 200 and r11.get_json()['success'], 'valid config rejected'

# Test themes and fonts
r12 = c.get('/api/themes')
print('GET /api/themes ->', r12.status_code, 'themes:', list(r12.get_json().keys()))

r13 = c.get('/api/fonts')
print('GET /api/fonts ->', r13.status_code, 'fonts:', list(r13.get_json().keys()))

# Test font serving
r14 = c.get('/assets/fonts/AtkinsonHyperlegible-Regular.ttf')
print('GET font ->', r14.status_code, 'content-type:', r14.content_type)

# Test health
r15 = c.get('/health')
print('GET /health ->', r15.status_code, r15.get_json())

# --- Access code gate (simulate web deployment) ---
routes.ACCESS_CODE = 'test-code-123'
os.environ['RENDER'] = '1'  # simulate web deployment

# Without code -> 403
r16 = run('print("hi")')
print('POST /api/run (no code) ->', r16.status_code, r16.get_json())
assert r16.status_code == 403 and r16.get_json().get('code_required'), 'access code not enforced'

# With wrong code -> 403
r17 = run('print("hi")', access_code='wrong')
print('POST /api/run (wrong code) ->', r17.status_code)
assert r17.status_code == 403, 'wrong access code accepted'

# With correct code -> 200
r18 = run('print("hi")', access_code='test-code-123')
print('POST /api/run (correct code) ->', r18.status_code, r18.get_json())
assert r18.status_code == 200, 'correct access code rejected'

# Config POST without code -> 403
r19 = settings(font='OpenDyslexic')
print('POST /api/config (no code) ->', r19.status_code)
assert r19.status_code == 403, 'config POST not gated by access code'

# Maintenance mode: web with NO access code set -> open (sandbox protects)
routes.ACCESS_CODE = ''
r20 = run('print("hi")')
print('POST /api/run (no code set) ->', r20.status_code, r20.get_json())
assert r20.status_code == 200, 'runner should be open when no access code is set'

# Sandbox still blocks dangerous code without an access code
r21 = run('import os')
print('POST /api/run (blocked, no code) ->', r21.get_json())
assert 'not allowed' in r21.get_json()['error'], 'sandbox not active without access code'

routes.ACCESS_CODE = 'test-code-123'
del os.environ['RENDER']

# --- Language switching, end to end ---
# The reader picks a language; the whole page and every sentence the server
# generates have to follow, in both directions of the switch.
routes.ACCESS_CODE = ''  # settings are open again on a local install
# The checks above used up the ten requests the rate limiter allows in a
# minute. Clearing the counter keeps this section about language rather
# than about the limiter, which is checked at the end.
routes.RATE_LIMIT.clear()
assert c.post('/api/config', json={'locale': 'en'}).status_code == 200
for code, run_label, explained_word, blocked_word in (
    ('fr', 'Exécuter', 'Vous divisez par zéro',
     "Ce code utilise une fonction qui n'est pas autorisée"),
    ('ar', 'تشغيل', 'أنت تقسم على صفر', 'تستخدم هذه الشيفرة ميزة غير مسموح بها'),
):
    assert settings(locale=code).status_code == 200, f'could not switch to {code}'
    page = c.get('/').get_data(as_text=True)
    saved = c.get('/api/config').get_json()['locale']
    # Both halves of the error path: the traceback explanation and the
    # message the server writes itself.
    explained = c.post('/api/run', json={'code': 'x = 1/0', 'locale': code}).get_json()['error']
    blocked = c.post('/api/run', json={'code': 'import os', 'locale': code}).get_json()['error']
    ok = (saved == code and run_label in page
          and f'<html lang="{code}">' in page
          and explained_word in explained and blocked_word in blocked)
    print(f'{code} page and server errors follow the reader ->', 'OK' if ok else f'FAILED {explained!r}')
    assert ok, f'{code} did not render throughout'

assert settings(locale='en').status_code == 200, 'could not switch back to English'
assert c.get('/api/config').get_json()['locale'] == 'en', 'did not return to English'
print('switched back to English -> OK')

# --- Rate limiter ---
# The runner is the part of the app that costs the most to abuse, so there
# is a cap on how often one caller may use it. It had no test at all.
routes.RATE_LIMIT.clear()
statuses = [c.post('/api/run', json={'code': 'pass', 'locale': 'en'}).status_code
            for _ in range(12)]
refused = sum(1 for s in statuses if s == 429)
print(f'POST /api/run x12 -> {statuses.count(200)} ran, {refused} refused')
assert statuses[0] == 200, 'the first request should be allowed'
assert refused > 0, 'the rate limiter never refused anything'
assert set(statuses) <= {200, 429}, f'unexpected statuses: {set(statuses)}'

del routes.CONFIG_DIR, routes.CONFIG_FILE
_tmp.cleanup()
sys.stdout.flush()
print('\nALL SMOKE TESTS PASSED')
