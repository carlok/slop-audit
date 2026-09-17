"""Adapter B: dslop."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from slop_audit.adapters.base import ROOT, run_cmd, write_raw
from slop_audit.models import CATEGORY_SLOP, ToolResult, ToolStatus
from slop_audit.normalize import normalize_from_counts

TOOL = "dslop"
VERSION = "0.2.2"
_BIN = ROOT / "envs" / "slop" / "bin" / "dslop"

_VIOLATION_LINE = re.compile(r"^\s+\S+:\d+:\d+\s+\S+")
_SUMMARY = re.compile(r"dslop:\s+(\d+)\s+violation", re.IGNORECASE)


def parse_stdout(stdout: str, word_count: int) -> dict[str, Any]:
    """Parse dslop text output; violations → warnings (no native 0–100)."""
    violations: list[str] = []
    for line in stdout.splitlines():
        if _VIOLATION_LINE.match(line):
            violations.append(line.strip())
    if not violations:
        m = _SUMMARY.search(stdout)
        n = int(m.group(1)) if m else 0
        warnings = n
    else:
        warnings = len(violations)
    errors = 0
    info = 0
    normalized = normalize_from_counts(errors, warnings, info, word_count)
    return {
        "native": {"stdout": stdout, "violations": violations, "violation_count": warnings},
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
    commands = [str(_BIN), str(path)]
    if not _BIN.is_file():
        return _not_run(f"missing binary: {_BIN}", commands)

    proc = run_cmd(commands, timeout=120)
    write_raw(TOOL, "stdout.txt", proc["stdout"])
    write_raw(TOOL, "stderr.txt", proc["stderr"])
    write_raw(TOOL, "returncode.txt", str(proc["returncode"]))

    # dslop exits non-zero when violations found; still OK if we got parseable output
    stdout = proc["stdout"] or ""
    stderr = proc["stderr"] or ""
    if not stdout.strip() and proc["returncode"] not in (0, 1):
        return ToolResult(
            tool=TOOL,
            status=ToolStatus.ERROR,
            version=VERSION,
            category=CATEGORY_SLOP,
            commands=commands,
            raw_dir=f"raw/{TOOL}",
            native={"returncode": proc["returncode"], "stderr": stderr},
            normalized_score=None,
            findings_count=0,
            errors=0,
            warnings=0,
            info=0,
            reason=f"dslop failed rc={proc['returncode']}: {stderr[:300]}",
        )

    try:
        parsed = parse_stdout(stdout, word_count)
    except (TypeError, ValueError) as e:
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

    write_raw(TOOL, "parsed.json", json.dumps(parsed["native"], indent=2) + "\n")
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
