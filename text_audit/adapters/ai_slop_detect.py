"""Adapter D: ai-slop-detect."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from text_audit.adapters.base import ROOT, run_cmd, write_raw
from text_audit.models import CATEGORY_SLOP, ToolResult, ToolStatus
from text_audit.normalize import normalize_from_counts

TOOL = "ai_slop_detect"
VERSION = "0.1.0"
_BIN = ROOT / "envs" / "slop" / "bin" / "ai-slop"


def parse_stdout(stdout: str, word_count: int) -> dict[str, Any]:
    """Parse ai-slop --json; prefer native ai_score 0–100."""
    data = json.loads(stdout)
    # CLI may emit one object or a list
    if isinstance(data, list):
        files = data
        primary = data[0] if data else {}
    else:
        files = [data]
        primary = data

    hits = 0
    for f in files:
        h = f.get("hits")
        if isinstance(h, list):
            hits += len(h)
        elif isinstance(f.get("stats"), dict):
            hits += int(f["stats"].get("hits") or 0)

    ai_score = primary.get("ai_score")
    if ai_score is None and files:
        scores = [f.get("ai_score") for f in files if f.get("ai_score") is not None]
        ai_score = max(scores) if scores else None

    errors = 0
    warnings = hits  # each hit is a stylistic tell → warning
    info = 0
    if ai_score is None:
        normalized = normalize_from_counts(errors, warnings, info, word_count)
    else:
        normalized = float(ai_score)

    return {
        "native": data,
        "errors": errors,
        "warnings": warnings,
        "info": info,
        "findings_count": hits,
        "normalized_score": normalized,
    }


def _not_run(reason: str, commands: list[str]) -> ToolResult:
    return ToolResult(
        tool=TOOL,
        status=ToolStatus.NOT_RUN,
        version=VERSION,
        category=CATEGORY_SLOP,
        commands=commands,
        raw_dir=f"raw/{TOOL}",
        native=None,
        normalized_score=None,
        findings_count=0,
        errors=0,
        warnings=0,
        info=0,
        reason=reason,
    )


def run(input_path: Path, word_count: int) -> ToolResult:
    path = Path(input_path)
    commands = [str(_BIN), "--json", str(path)]
    if not _BIN.is_file():
        return _not_run(f"missing binary: {_BIN}", commands)

    proc = run_cmd(commands, timeout=120)
    write_raw(TOOL, "stdout.txt", proc["stdout"])
    write_raw(TOOL, "stderr.txt", proc["stderr"])
    write_raw(TOOL, "returncode.txt", str(proc["returncode"]))

    stdout = (proc["stdout"] or "").strip()
    if not stdout:
        return ToolResult(
            tool=TOOL,
            status=ToolStatus.ERROR,
            version=VERSION,
            category=CATEGORY_SLOP,
            commands=commands,
            raw_dir=f"raw/{TOOL}",
            native={"returncode": proc["returncode"]},
            normalized_score=None,
            findings_count=0,
            errors=0,
            warnings=0,
            info=0,
            reason=f"empty stdout (rc={proc['returncode']}): {(proc['stderr'] or '')[:300]}",
        )

    try:
        parsed = parse_stdout(stdout, word_count)
    except (json.JSONDecodeError, TypeError, ValueError, KeyError) as e:
        return ToolResult(
            tool=TOOL,
            status=ToolStatus.ERROR,
            version=VERSION,
            category=CATEGORY_SLOP,
            commands=commands,
            raw_dir=f"raw/{TOOL}",
            native=None,
            normalized_score=None,
            findings_count=0,
            errors=0,
            warnings=0,
            info=0,
            reason=f"parse error: {type(e).__name__}: {e}",
        )

    write_raw(TOOL, "result.json", json.dumps(parsed["native"], indent=2) + "\n")
    return ToolResult(
        tool=TOOL,
        status=ToolStatus.OK,
        version=VERSION,
        category=CATEGORY_SLOP,
        commands=commands,
        raw_dir=f"raw/{TOOL}",
        native=parsed["native"],
        normalized_score=parsed["normalized_score"],
        findings_count=parsed["findings_count"],
        errors=parsed["errors"],
        warnings=parsed["warnings"],
        info=parsed["info"],
        reason="",
    )


run.tool = TOOL  # type: ignore[attr-defined]
run.version = VERSION  # type: ignore[attr-defined]
