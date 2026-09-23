"""Smoke test for AccessibleIDE."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from accessible_ide import create_app

app = create_app()
c = app.test_client()

# Test index page
r = c.get('/')
print('GET / ->', r.status_code, '(len:', len(r.data), ')')

# Test run code (success)
r2 = c.post('/api/run', json={'code': 'print("hello")'})
print('POST /api/run ->', r2.status_code, r2.get_json())

# Test run code (error)
r3 = c.post('/api/run', json={'code': 'x = 1/0'})
print('POST /api/run (error) ->', r3.get_json())

# Test run code (syntax error)
r4 = c.post('/api/run', json={'code': 'def foo(:\n    pass'})
print('POST /api/run (syntax) ->', r4.get_json())

# Test config
r5 = c.get('/api/config')
print('GET /api/config ->', r5.status_code, r5.get_json())

r6 = c.post('/api/config', json={'font': 'OpenDyslexic'})
print('POST /api/config ->', r6.status_code, r6.get_json())

# Test themes and fonts
r7 = c.get('/api/themes')
print('GET /api/themes ->', r7.status_code, 'themes:', list(r7.get_json().keys()))

r8 = c.get('/api/fonts')
print('GET /api/fonts ->', r8.status_code, 'fonts:', list(r8.get_json().keys()))

# Test font serving
r9 = c.get('/assets/fonts/AtkinsonHyperlegible-Regular.ttf')
print('GET font ->', r9.status_code, 'content-type:', r9.content_type)

# Test health
r10 = c.get('/health')
print('GET /health ->', r10.status_code, r10.get_json())

print('\nALL SMOKE TESTS PASSED')