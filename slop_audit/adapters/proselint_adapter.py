"""Adapter G: proselint."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from slop_audit.adapters.base import ROOT, run_cmd, write_raw
from slop_audit.models import CATEGORY_PROSE, ToolResult, ToolStatus
from slop_audit.normalize import normalize_from_counts

TOOL = "proselint"
VERSION = "0.16.0"
_BIN = ROOT / "envs" / "slop" / "bin" / "proselint"


def parse_stdout(stdout: str, word_count: int) -> dict[str, Any]:
    """Parse proselint -o json; each diagnostic → warning."""
    data = json.loads(stdout)
    diagnostics: list[dict[str, Any]] = []
    result = data.get("result") or {}
    if isinstance(result, dict):
        for _uri, block in result.items():
            if isinstance(block, dict):
                diags = block.get("diagnostics") or []
                if isinstance(diags, list):
                    diagnostics.extend(d for d in diags if isinstance(d, dict))
    warnings = len(diagnostics)
    errors = 0
    info = 0
    normalized = normalize_from_counts(errors, warnings, info, word_count)
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
    commands = [str(_BIN), "check", "-o", "json", str(path)]
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
            category=CATEGORY_PROSE,
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
        write_raw(TOOL, "parse_error.txt", f"{type(e).__name__}: {e}\n{stdout[:2000]}")
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
