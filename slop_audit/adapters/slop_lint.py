"""Adapter E: slop-lint (invoke via node; .bin symlink skips main)."""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from slop_audit.adapters.base import ROOT, run_cmd, write_raw
from slop_audit.models import CATEGORY_SLOP, ToolResult, ToolStatus
from slop_audit.normalize import normalize_from_counts

TOOL = "slop_lint"
VERSION = "0.6.0"
_SCRIPT = ROOT / "tools" / "node_modules" / "slop-lint" / "slop-lint.mjs"

_SUMMARY = re.compile(
    r"(\d+)\s+em-dash failure\(s\),\s+(\d+)\s+warning\(s\)",
    re.IGNORECASE,
)
_FAIL_LINE = re.compile(r"^\s+\d+:\s+✗")
_WARN_LINE = re.compile(r"^\s+\d+:\s+⚠")


def parse_stdout(stdout: str, word_count: int) -> dict[str, Any]:
    """Parse slop-lint text; em-dash failures → errors, ⚠ → warnings."""
    errors = warnings = 0
    m = _SUMMARY.search(stdout)
    if m:
        errors = int(m.group(1))
        warnings = int(m.group(2))
    else:
        for line in stdout.splitlines():
            if _FAIL_LINE.match(line):
                errors += 1
            elif _WARN_LINE.match(line):
                warnings += 1

    info = 0
    normalized = normalize_from_counts(errors, warnings, info, word_count)
    return {
        "native": {"stdout": stdout, "em_dash_failures": errors, "warnings": warnings},
        "errors": errors,
        "warnings": warnings,
        "info": info,
        "findings_count": errors + warnings + info,
        "normalized_score": normalized,
    }


def _node() -> str | None:
    return shutil.which("node")


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
    node = _node()
    commands = [node or "node", str(_SCRIPT), str(path)]
    if node is None:
        return _not_run("missing binary: node", commands)
    if not _SCRIPT.is_file():
        return _not_run(f"missing module: {_SCRIPT}", commands)

    proc = run_cmd(commands, timeout=120)
    write_raw(TOOL, "stdout.txt", proc["stdout"])
    write_raw(TOOL, "stderr.txt", proc["stderr"])
    write_raw(TOOL, "returncode.txt", str(proc["returncode"]))

    stdout = proc["stdout"] or ""
    # exit 1 = em-dash failures present; still parseable
    if proc["returncode"] not in (0, 1) and not stdout.strip():
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
            reason=f"slop-lint rc={proc['returncode']}: {(proc['stderr'] or '')[:300]}",
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
