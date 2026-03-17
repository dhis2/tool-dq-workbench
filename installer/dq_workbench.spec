# installer/dq_workbench.spec
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main_win.py'],
    pathex=['..'],          # project root — so 'app.web.app' resolves correctly
    binaries=[],
    datas=[
        ('../app/web/templates', 'app/web/templates'),
        ('../app/web/static',    'app/web/static'),
    ],
    hiddenimports=[
        'waitress',
        'waitress.utilities',
        'flask_wtf',
        'pkg_resources',
        'pkg_resources.extern',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['gunicorn'],  # gunicorn is Linux-only; exclude from the Windows bundle
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
    name='dq-workbench',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,           # Keep console window — closing it stops the server
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='dq-workbench',
)
