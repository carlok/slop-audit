"""Adapter F: Vale (write-good package + custom Slop rules)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from text_audit.adapters.base import ROOT, run_cmd, write_raw
from text_audit.models import CATEGORY_PROSE, ToolResult, ToolStatus
from text_audit.normalize import normalize_from_counts

TOOL = "vale"
VERSION = "3.21.0"
_BIN = ROOT / "tools" / "vale" / "vale"
_CONFIG = ROOT / "vale" / ".vale.ini"

_SEV = {
    "error": "errors",
    "warning": "warnings",
    "warn": "warnings",
    "suggestion": "info",
    "note": "info",
    "info": "info",
}


def parse_stdout(stdout: str, word_count: int) -> dict[str, Any]:
    """Parse Vale --output=JSON into severity counts + normalized score."""
    data = json.loads(stdout) if stdout.strip() else {}
    if not isinstance(data, dict):
        data = {}
    errors = warnings = info = 0
    alerts: list[dict[str, Any]] = []
    for _path, items in data.items():
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            alerts.append(item)
            sev = str(item.get("Severity") or "warning").lower()
            bucket = _SEV.get(sev, "warnings")
            if bucket == "errors":
                errors += 1
            elif bucket == "warnings":
                warnings += 1
            else:
                info += 1
    normalized = normalize_from_counts(errors, warnings, info, word_count)
    return {
        "native": {"alerts": alerts, "by_file": data},
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
    commands = [
        str(_BIN),
        f"--config={_CONFIG}",
        "--output=JSON",
        str(path),
    ]
    if not _BIN.is_file():
        return _not_run(f"missing binary: {_BIN}", commands)
    if not _CONFIG.is_file():
        return _not_run(f"missing config: {_CONFIG}", commands)

    proc = run_cmd(commands, timeout=120)
    write_raw(TOOL, "stdout.txt", proc["stdout"])
    write_raw(TOOL, "stderr.txt", proc["stderr"])
    write_raw(TOOL, "returncode.txt", str(proc["returncode"]))

    stdout = proc["stdout"] or ""
    # Vale exits non-zero when alerts present; empty {} is still valid
    if proc["returncode"] not in (0, 1) and not stdout.strip():
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
            reason=f"vale rc={proc['returncode']}: {(proc['stderr'] or '')[:300]}",
        )

    try:
        parsed = parse_stdout(stdout if stdout.strip() else "{}", word_count)
    except (json.JSONDecodeError, TypeError, ValueError) as e:
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
