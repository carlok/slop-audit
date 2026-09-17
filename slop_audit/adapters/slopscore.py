"""Adapter A: SlopScore (slopscore-lint)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from slop_audit.adapters.base import ROOT, run_cmd, write_raw
from slop_audit.models import CATEGORY_SLOP, ToolResult, ToolStatus
from slop_audit.normalize import normalize_from_counts

TOOL = "slopscore"
VERSION = "0.13.0"
_BIN = ROOT / "envs" / "slop" / "bin" / "slopscore-lint"

_SEV_MAP = {
    "high": "errors",
    "error": "errors",
    "medium": "warnings",
    "warning": "warnings",
    "warn": "warnings",
    "low": "info",
    "info": "info",
}


def parse_stdout(stdout: str, word_count: int) -> dict[str, Any]:
    """Parse slopscore-lint JSON stdout into counts + native score."""
    data = json.loads(stdout)
    evidence = data.get("evidence") or []
    errors = warnings = info = 0
    for item in evidence:
        sev = str(item.get("severity") or "info").lower()
        bucket = _SEV_MAP.get(sev, "info")
        if bucket == "errors":
            errors += 1
        elif bucket == "warnings":
            warnings += 1
        else:
            info += 1
    score_block = data.get("score") or {}
    native_score = score_block.get("slop_score")
    if native_score is None:
        normalized = normalize_from_counts(errors, warnings, info, word_count)
    else:
        normalized = float(native_score)
    return {
        "native": data,
        "errors": errors,
        "warnings": warnings,
        "info": info,
        "findings_count": errors + warnings + info,
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
    commands = [str(_BIN), "scan", "-f", "json", str(path)]
    if not _BIN.is_file():
        return _not_run(f"missing binary: {_BIN}", commands)

    proc = run_cmd(commands, timeout=120)
    write_raw(TOOL, "stdout.txt", proc["stdout"])
    write_raw(TOOL, "stderr.txt", proc["stderr"])
    write_raw(TOOL, "returncode.txt", str(proc["returncode"]))

    stdout = proc["stdout"].strip()
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
            reason=f"empty stdout (rc={proc['returncode']}): {proc['stderr'][:300]}",
        )

    try:
        parsed = parse_stdout(stdout, word_count)
    except (json.JSONDecodeError, TypeError, KeyError, ValueError) as e:
        write_raw(TOOL, "parse_error.txt", f"{type(e).__name__}: {e}\n{stdout[:2000]}")
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
        version=str(parsed["native"].get("version") or VERSION),
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
