# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


project_root = Path(SPECPATH).resolve()


def pick_first_existing(*candidates):
    for candidate in candidates:
        p = project_root / candidate
        if p.exists():
            return str(p)
    return None


icon_path = pick_first_existing('icon.ico', 'icon.png')

a = Analysis(
    ['main.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        ('templates', 'templates'),
        ('static', 'static'),
        ('instance', 'instance'),
    ],
    hiddenimports=[
        'flask',
        'flask_login',
        'flask_migrate',
        'flask_sqlalchemy',
        'flask_wtf',
        'sqlalchemy',
        'werkzeug',
        'requests',
        'urllib3',
        'certifi',
        'bs4',
        'pandas',
        'plotly',
        'plotly.express',
        'plotly.graph_objects',
        'dotenv',
        'ttkbootstrap',
        'pystray',
        'PIL',
        'PIL.Image',
        'PIL.ImageTk',
        'psutil',
    ],
    hookspath=['hooks'],
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
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
)
