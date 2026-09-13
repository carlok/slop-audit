"""Adapter J: LanguageTool local distribution only."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from text_audit.adapters.base import ROOT, run_cmd, write_raw
from text_audit.models import CATEGORY_PROSE, ToolResult, ToolStatus
from text_audit.normalize import normalize_from_counts

TOOL = "languagetool"
VERSION = "6.6"
_LT_ROOT = ROOT / "tools" / "languagetool"
_JAR = _LT_ROOT / "LanguageTool-6.6" / "languagetool-commandline.jar"

# misspellings → info; everything else → warning
_INFO_TYPES = frozenset({"misspelling", "typographical", "uncategorized"})


def _find_jar() -> Path | None:
    if _JAR.is_file():
        return _JAR
    matches = sorted(_LT_ROOT.glob("LanguageTool-*/languagetool-commandline.jar"))
    return matches[0] if matches else None


def parse_stdout(stdout: str, word_count: int) -> dict[str, Any]:
    """Parse LanguageTool --json; map issueType to severities."""
    data = json.loads(stdout)
    matches = data.get("matches") or []
    if not isinstance(matches, list):
        matches = []
    errors = warnings = info = 0
    for m in matches:
        if not isinstance(m, dict):
            continue
        rule = m.get("rule") or {}
        issue = str(rule.get("issueType") or "").lower()
        if issue in _INFO_TYPES:
            info += 1
        else:
            warnings += 1
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
    java = shutil.which("java")
    jar = _find_jar()
    commands = [
        java or "java",
        "-jar",
        str(jar or _JAR),
        "-l",
        "en-US",
        "--json",
        str(path),
    ]
    if java is None:
        return _not_run("missing binary: java", commands)
    if jar is None:
        return _not_run(f"missing local LanguageTool jar under {_LT_ROOT}", commands)

    proc = run_cmd(commands, timeout=300)
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

    ver = VERSION
    soft = (parsed["native"] or {}).get("software") if isinstance(parsed["native"], dict) else None
    if isinstance(soft, dict) and soft.get("version"):
        ver = str(soft["version"])

    write_raw(TOOL, "parsed.json", json.dumps({"match_count": parsed["findings_count"]}, indent=2) + "\n")
    return ToolResult(
        tool=TOOL,
        status=ToolStatus.OK,
        version=ver,
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
        notes="local LanguageTool only (no cloud API)",
    )


run.tool = TOOL  # type: ignore[attr-defined]
run.version = VERSION  # type: ignore[attr-defined]
