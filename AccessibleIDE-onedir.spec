# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller onedir spec for AccessibleIDE Windows installer build.

Produces dist/AccessibleIDE/ (folder with exe + _internal/).
A folder install is more reliable than onefile: no temp extraction,
faster startup, and fewer antivirus false positives.
"""

import os

block_cipher = None

# Collect static assets, templates, and fonts
datas = [
    ('src/accessible_ide/static', 'accessible_ide/static'),
    ('src/accessible_ide/templates', 'accessible_ide/templates'),
    ('src/accessible_ide/assets', 'accessible_ide/assets'),
]

a = Analysis(
    ['app.py'],
    pathex=['src'],
    binaries=[],
    datas=datas,
    hiddenimports=['flask', 'jinja2', 'werkzeug'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'unittest', 'pydoc'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AccessibleIDE',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # Windowed app (no console)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='src/accessible_ide/assets/icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AccessibleIDE',
)