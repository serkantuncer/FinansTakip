import os
import sys
from pathlib import Path


def _prepend_env_path(env_key: str, path_value: Path) -> None:
    if not path_value.exists():
        return
    current = os.environ.get(env_key, "")
    os.environ[env_key] = f"{path_value}{os.pathsep}{current}" if current else str(path_value)


base_dir = Path(getattr(sys, "_MEIPASS", Path.cwd()))

dll_dirs = [
    base_dir / "gtk" / "bin",
    base_dir / "msys64" / "mingw64" / "bin",
]

for dll_dir in dll_dirs:
    if dll_dir.exists():
        _prepend_env_path("PATH", dll_dir)
        try:
            os.add_dll_directory(str(dll_dir))
        except Exception:
            pass

# Fontconfig dosyaları varsa ortam değişkenlerini ayarla.
fontconfig_dir = base_dir / "gtk" / "etc" / "fonts"
fontconfig_file = fontconfig_dir / "fonts.conf"
if fontconfig_dir.exists():
    os.environ.setdefault("FONTCONFIG_PATH", str(fontconfig_dir))
if fontconfig_file.exists():
    os.environ.setdefault("FONTCONFIG_FILE", str(fontconfig_file))
