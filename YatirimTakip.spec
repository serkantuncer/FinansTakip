# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('templates', 'templates'), 
        ('static', 'static'), 
        ('instance/finans_takip.db', 'instance'),
        ('instance', 'instance')  # Tüm instance klasörünü ekle
    ],
    hiddenimports=[
        'sqlite3',  # SQLite modülünü ekle
        'flask',
        'flask_login',  # EKLENDİ
        'werkzeug',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='FinansTakipSistemi',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # macOS için False, Windows debug için True yapabilirsiniz
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',
)

# macOS için .app bundle
app = BUNDLE(
    exe,
    name='FinansTakipSistemi.app',
    icon='icon.icns',
    bundle_identifier='com.FinansTakipSistemi.app',
)