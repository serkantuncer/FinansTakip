# -*- mode: python ; coding: utf-8 -*-
import os
import sys

# Sanal ortam yolunu belirle
venv_path = '/Users/serkan/Documents/serkan_python/pythonRepo_MACOS/yatirim_yonetimi/FinancialSecurePortal_Yeni/.venv'
site_packages = os.path.join(venv_path, 'lib/python3.13/site-packages')

# WeasyPrint ve bağımlılıklarını manuel ekle
weasyprint_packages = []
packages_to_include = [
    'weasyprint',
    'cairocffi', 
    'cffi',
    'cssselect2',
    'tinycss2',
    'html5lib',
    'fonttools',
    'pyphen'
]

for package in packages_to_include:
    package_path = os.path.join(site_packages, package)
    if os.path.exists(package_path):
        weasyprint_packages.append((package_path, package))
        print(f"✓ {package} eklendi: {package_path}")
    else:
        print(f"✗ {package} bulunamadı: {package_path}")

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('templates', 'templates'), 
        ('static', 'static'), 
        ('instance/finans_takip.db', 'instance'),
        ('instance', 'instance'),
        *weasyprint_packages,  # WeasyPrint paketlerini ekle
    ],
    hiddenimports=[
        'sqlite3',
        'flask',
        'flask_login',
        'werkzeug',
        'flask_sqlalchemy',
        'flask_migrate',
        'werkzeug.security',
        'requests',
        'bs4',
        'pandas',
        'decimal',
        'plotly',
        'plotly.express',
        'plotly.graph_objects',
        # WeasyPrint bağımlılıkları
        'weasyprint',
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
    console=False,
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