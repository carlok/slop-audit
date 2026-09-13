"""Adapter C: SlopSift (writinglint / slopsift)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from text_audit.adapters.base import ROOT, run_cmd, write_raw
from text_audit.models import CATEGORY_SLOP, ToolResult, ToolStatus
from text_audit.normalize import normalize_from_counts

TOOL = "slopsift"
VERSION = "0.11.0"
_BIN = ROOT / "tools" / "node_modules" / ".bin" / "slopsift"


def parse_stdout(stdout: str, word_count: int) -> dict[str, Any]:
    """Parse slopsift JSON (--format json); use counts, no native 0–100."""
    data = json.loads(stdout)
    if isinstance(data, list):
        files = data
    elif isinstance(data, dict):
        files = [data]
    else:
        files = []

    errors = warnings = info = 0
    for f in files:
        errors += int(f.get("errorCount") or 0)
        warnings += int(f.get("warningCount") or 0)
        info += int(f.get("infoCount") or 0)
        # Fallback: derive from messages if counts absent/zero but messages present
        if (
            not (f.get("errorCount") or f.get("warningCount") or f.get("infoCount"))
            and f.get("messages")
        ):
            for msg in f["messages"]:
                level = str(msg.get("level") or "").lower()
                if level in ("error", "errors"):
                    errors += 1
                elif level in ("warn", "warning", "warnings"):
                    warnings += 1
                else:
                    info += 1

    normalized = normalize_from_counts(errors, warnings, info, word_count)
    return {
        "native": data,
        "errors": errors,
        "warnings": warnings,
        "info": info,
        "findings_count": errors + warnings + info,
        "normalized_score": normalized,
    }


def _resolve_bin() -> Path | None:
    if _BIN.is_file():
        return _BIN
    which = shutil.which("slopsift")
    return Path(which) if which else None


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
    bin_path = _resolve_bin()
    commands = [
        str(bin_path or "slopsift"),
        "--format",
        "json",
        "--ext",
        ".txt,.md,.markdown,.mdx",
        "--exit-zero",
        str(path),
    ]
    if bin_path is None:
        return _not_run("missing binary: slopsift (tools/node_modules/.bin/slopsift)", commands)

    proc = run_cmd(commands, timeout=180)
    write_raw(TOOL, "stdout.txt", proc["stdout"])
    write_raw(TOOL, "stderr.txt", proc["stderr"])
    write_raw(TOOL, "returncode.txt", str(proc["returncode"]))

    stdout = (proc["stdout"] or "").strip()
    stderr = proc["stderr"] or ""

    # Node engines warning / hard failure
    if proc["returncode"] not in (0, 1) and not stdout:
        reason = stderr.strip() or f"slopsift rc={proc['returncode']}"
        # engines.node mismatch often still runs; treat hard failure as ERROR/NOT_RUN
        status = ToolStatus.NOT_RUN if "ENGINES" in stderr.upper() or "engine" in stderr.lower() else ToolStatus.ERROR
        if "Cannot find module" in stderr or "not found" in stderr.lower():
            status = ToolStatus.NOT_RUN
        return ToolResult(
            tool=TOOL,
            status=status,
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
            reason=reason[:500],
        )

    if not stdout:
        # clean run with no output — treat as OK zero findings
        parsed = {
            "native": [],
            "errors": 0,
            "warnings": 0,
            "info": 0,
            "findings_count": 0,
            "normalized_score": normalize_from_counts(0, 0, 0, word_count),
        }
    else:
        try:
            parsed = parse_stdout(stdout, word_count)
        except (json.JSONDecodeError, TypeError, ValueError) as e:
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
    notes = ""
    if stderr.strip():
        notes = stderr.strip()[:300]
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
        notes=notes,
    )


run.tool = TOOL  # type: ignore[attr-defined]
run.version = VERSION  # type: ignore[attr-defined]
