#!/usr/bin/env python3
"""Write environment inspection JSON to logs/environment.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from slop_audit.env_inspect import inspect_environment  # noqa: E402


def main() -> None:
    out = ROOT / "logs" / "environment.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    data = inspect_environment()
    out.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
