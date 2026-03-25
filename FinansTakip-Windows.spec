# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, collect_dynamic_libs


project_root = Path(SPECPATH).resolve()


def pick_first_existing(*candidates):
    for candidate in candidates:
        p = project_root / candidate
        if p.exists():
            return str(p)
    return None


icon_path = pick_first_existing('icon.ico', 'icon.png')

weasyprint_datas = []
for package_name in ['weasyprint', 'tinycss2', 'cssselect2', 'pyphen', 'fontTools']:
    weasyprint_datas.extend(collect_data_files(package_name, include_py_files=True))

weasyprint_hiddenimports = []
for package_name in ['weasyprint', 'tinycss2', 'cssselect2', 'pyphen', 'fontTools']:
    weasyprint_hiddenimports.extend(collect_submodules(package_name))

# Numpy C-extension/DLL dosyalarini one-file build'e acikca ekle.
numpy_binaries = collect_dynamic_libs('numpy')
# Pandas import zincirinde one-file icin gerekli numpy alt modulleri.
numpy_hiddenimports = [
    'numpy._core._exceptions',
    'numpy._core._multiarray_umath',
    'numpy._core._dtype_ctypes',
]

# WeasyPrint'in Windows'ta ihtiyaç duyduğu GTK/Cairo/Pango DLL'lerini paketle.
extra_binaries = []
extra_datas = []

gtk_root = Path(r"C:\Program Files\GTK3-Runtime Win64")
if gtk_root.exists():
    extra_binaries.append((str(gtk_root / "bin" / "*.dll"), "gtk/bin"))
    if (gtk_root / "etc").exists():
        extra_datas.append((str(gtk_root / "etc"), "gtk/etc"))
    if (gtk_root / "share").exists():
        extra_datas.append((str(gtk_root / "share"), "gtk/share"))

msys_root = Path(r"C:\msys64\mingw64")
if msys_root.exists():
    extra_binaries.append((str(msys_root / "bin" / "*.dll"), "msys64/mingw64/bin"))

a = Analysis(
    ['main.py'],
    pathex=[str(project_root)],
    binaries=extra_binaries + numpy_binaries,
    datas=[
        ('templates', 'templates'),
        ('static', 'static'),
        ('instance', 'instance'),
        ('icon.png', '.'),
        ('icon.ico', '.'),
    ] + weasyprint_datas + extra_datas,
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
        'weasyprint',
        'pydyf',
        'tinyhtml5',
        'tinycss2',
        'cssselect2',
        'pyphen',
        'fontTools',
    ] + weasyprint_hiddenimports + numpy_hiddenimports,
    hookspath=['hooks'],
    hooksconfig={},
    runtime_hooks=['hooks/rthook_weasyprint_runtime.py'],
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
    upx=False,
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
