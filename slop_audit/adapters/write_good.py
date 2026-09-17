"""Adapter H: write-good (npm)."""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from slop_audit.adapters.base import ROOT, run_cmd, write_raw
from slop_audit.models import CATEGORY_PROSE, ToolResult, ToolStatus
from slop_audit.normalize import normalize_from_counts

TOOL = "write_good"
VERSION = "1.0.8"
_BIN = ROOT / "tools" / "node_modules" / ".bin" / "write-good"

# path:line:col:message
_LINE = re.compile(r"^[^:\n]+:\d+:\d+:.+")


def parse_stdout(stdout: str, word_count: int) -> dict[str, Any]:
    """Parse write-good --parse lines; each finding → warning."""
    findings = [ln for ln in stdout.splitlines() if _LINE.match(ln.strip())]
    warnings = len(findings)
    errors = 0
    info = 0
    normalized = normalize_from_counts(errors, warnings, info, word_count)
    return {
        "native": {"stdout": stdout, "findings": findings},
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
        category=CATEGORY_PROSE,
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
    bin_path = _BIN if _BIN.is_file() else None
    if bin_path is None:
        which = shutil.which("write-good")
        bin_path = Path(which) if which else None
    commands = [str(bin_path or _BIN), "--parse", str(path)]
    if bin_path is None or not Path(bin_path).is_file():
        return _not_run(f"missing binary: {_BIN}", commands)

    proc = run_cmd(commands, timeout=120)
    write_raw(TOOL, "stdout.txt", proc["stdout"])
    write_raw(TOOL, "stderr.txt", proc["stderr"])
    write_raw(TOOL, "returncode.txt", str(proc["returncode"]))

    stdout = proc["stdout"] or ""
    # write-good --parse exits non-zero when findings exist (0/1/255).
    # Hard failures often emit stderr only — treat empty stdout + bad rc as ERROR.
    if proc["returncode"] not in (0, 1, 255) and not stdout.strip():
        return ToolResult(
            tool=TOOL,
            status=ToolStatus.ERROR,
            version=VERSION,
            category=CATEGORY_PROSE,
            commands=commands,
            raw_dir=f"raw/{TOOL}",
            native={"returncode": proc["returncode"], "stderr": (proc["stderr"] or "")[:500]},
            normalized_score=None,
            findings_count=0,
            errors=0,
            warnings=0,
            info=0,
            reason=f"write-good rc={proc['returncode']}: {(proc['stderr'] or '')[:300]}",
        )

    try:
        parsed = parse_stdout(stdout, word_count)
    except (TypeError, ValueError) as e:
        return ToolResult(
            tool=TOOL,
            status=ToolStatus.ERROR,
            version=VERSION,
            category=CATEGORY_PROSE,
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
        category=CATEGORY_PROSE,
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
