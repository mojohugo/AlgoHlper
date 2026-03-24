from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def read_text_file(path: str | Path) -> str:
    file_path = Path(path)
    for encoding in ("utf-8", "utf-8-sig"):
        try:
            return file_path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return file_path.read_text(encoding="utf-8", errors="replace")
