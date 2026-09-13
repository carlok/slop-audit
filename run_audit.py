#!/usr/bin/env python3
"""CLI entrypoint: python run_audit.py [--force] [path]."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from text_audit.runner import run_audit  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the text-audit harness")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-run tools even when raw/<tool>/meta.json cache matches",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=str(ROOT / "input" / "target.txt"),
        help="Input text path (default: input/target.txt)",
    )
    args = parser.parse_args(argv)
    out = run_audit(args.path, force=args.force)
    report = out.get("report") or {}
    print(report.get("md") or out.get("normalized_results") or "done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
