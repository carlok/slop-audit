from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


def append_log(path: str | Path, message: str) -> None:
    """Append a timestamped line to path, creating parent directories as needed."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"{ts} {message}\n"
    with p.open("a", encoding="utf-8") as f:
        f.write(line)
