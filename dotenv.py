"""Minimal python-dotenv compatibility helpers.

This local module intentionally provides a subset of `python-dotenv` APIs
(`find_dotenv`, `dotenv_values`, `load_dotenv`) so Flask CLI can work even when
this file shadows the external package name.
"""

import os
from pathlib import Path
from typing import Dict, Optional


def _parse_dotenv(path: Path, encoding: str = "utf-8") -> Dict[str, Optional[str]]:
    data: Dict[str, Optional[str]] = {}
    if not path.exists() or not path.is_file():
        return data

    for raw_line in path.read_text(encoding=encoding).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if "=" not in line:
            data[line] = None
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            data[key] = value

    return data


def find_dotenv(filename: str = ".env", usecwd: bool = False) -> str:
    start = Path.cwd() if usecwd else Path(__file__).resolve().parent
    for current in [start, *start.parents]:
        candidate = current / filename
        if candidate.exists() and candidate.is_file():
            return str(candidate)
    return ""


def dotenv_values(
    dotenv_path: Optional[str] = None,
    encoding: str = "utf-8",
    **_: object,
) -> Dict[str, Optional[str]]:
    target = Path(dotenv_path) if dotenv_path else Path(find_dotenv(".env", usecwd=True))
    return _parse_dotenv(target, encoding=encoding)


def load_dotenv(
    dotenv_path: str = ".env",
    override: bool = False,
    encoding: str = "utf-8",
    **_: object,
) -> bool:
    data = dotenv_values(dotenv_path=dotenv_path, encoding=encoding)
    if not data:
        return False

    for key, value in data.items():
        if value is None:
            continue
        if override or key not in os.environ:
            os.environ[key] = value

    return True
