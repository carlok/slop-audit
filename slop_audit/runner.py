"""Orchestrate adapters, restartable raw cache, scoring, and reports."""
from __future__ import annotations

import json
import traceback
from pathlib import Path
from typing import Any, Callable

from slop_audit.adapters import get_adapters
from slop_audit.adapters.base import ROOT as _DEFAULT_ROOT
from slop_audit.env_inspect import inspect_environment
from slop_audit.input_stats import compute_input_stats
from slop_audit.logging_util import append_log
from slop_audit.models import (
    CATEGORY_STATS,
    ToolResult,
    ToolStatus,
)
from slop_audit.phenomena import corroborated_findings
from slop_audit.report import write_reports
from slop_audit.scoring_ai import compute_ai_likeness
from slop_audit.scoring_slop import compute_slop_index

ROOT: Path = _DEFAULT_ROOT

META_NAME = "meta.json"
RESULT_NAME = "result.json"


def _tool_name(adapter: Callable[..., Any]) -> str:
    name = getattr(adapter, "tool", None)
    if isinstance(name, str) and name:
        return name
    return getattr(adapter, "__name__", "unknown")


def _tool_version(adapter: Callable[..., Any]) -> str | None:
    ver = getattr(adapter, "version", None)
    if ver is None:
        return None
    return str(ver)


def _meta_path(tool: str) -> Path:
    return ROOT / "raw" / tool / META_NAME


def _result_path(tool: str) -> Path:
    return ROOT / "raw" / tool / RESULT_NAME


def _tool_result_from_dict(d: dict[str, Any]) -> ToolResult:
    status = d.get("status", ToolStatus.ERROR)
    if isinstance(status, str):
        status = ToolStatus(status)
    return ToolResult(
        tool=d["tool"],
        status=status,
        version=d.get("version"),
        category=d.get("category", ""),
        commands=list(d.get("commands") or []),
        raw_dir=d.get("raw_dir") or f"raw/{d['tool']}",
        native=d.get("native"),
        normalized_score=d.get("normalized_score"),
        findings_count=int(d.get("findings_count") or 0),
        errors=int(d.get("errors") or 0),
        warnings=int(d.get("warnings") or 0),
        info=int(d.get("info") or 0),
        reason=d.get("reason") or "",
        notes=d.get("notes") or "",
    )


def _write_cache(result: ToolResult, input_sha256: str) -> None:
    raw = ROOT / "raw" / result.tool
    raw.mkdir(parents=True, exist_ok=True)
    payload = result.to_dict()
    meta = {
        "tool": result.tool,
        "sha256": input_sha256,
        "input_sha256": input_sha256,
        "version": result.version,
        "status": result.status.value
        if isinstance(result.status, ToolStatus)
        else str(result.status),
    }
    (raw / META_NAME).write_text(
        json.dumps(meta, indent=2, default=str) + "\n", encoding="utf-8"
    )
    (raw / RESULT_NAME).write_text(
        json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8"
    )


def _load_cached(tool: str) -> ToolResult | None:
    result_file = _result_path(tool)
    if not result_file.is_file():
        return None
    try:
        data = json.loads(result_file.read_text(encoding="utf-8"))
        return _tool_result_from_dict(data)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None


def _cache_hit(
    tool: str, input_sha256: str, version: str | None, force: bool
) -> ToolResult | None:
    if force:
        return None
    meta_file = _meta_path(tool)
    if not meta_file.is_file():
        return None
    try:
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    status = meta.get("status")
    if status != ToolStatus.OK.value and status != ToolStatus.OK:
        return None
    sha = meta.get("sha256") or meta.get("input_sha256")
    if sha != input_sha256:
        return None
    if meta.get("version") != version:
        return None
    return _load_cached(tool)


def _error_result(tool: str, version: str | None, exc: BaseException) -> ToolResult:
    return ToolResult(
        tool=tool,
        status=ToolStatus.ERROR,
        version=version,
        category="",
        commands=[],
        raw_dir=f"raw/{tool}",
        native=None,
        normalized_score=None,
        findings_count=0,
        errors=0,
        warnings=0,
        info=0,
        reason=f"{type(exc).__name__}: {exc}",
        notes=traceback.format_exc(limit=5),
    )


def _run_one(
    adapter: Callable[..., Any],
    input_path: Path,
    word_count: int,
    input_sha256: str,
    force: bool,
    log_path: Path,
) -> tuple[ToolResult, bool]:
    """Return (result, skipped)."""
    tool = _tool_name(adapter)
    version = _tool_version(adapter)
    cached = _cache_hit(tool, input_sha256, version, force)
    if cached is not None:
        append_log(log_path, f"SKIP {tool} (cache hit sha={input_sha256[:12]}… ver={version})")
        return cached, True

    append_log(log_path, f"RUN {tool} force={force}")
    try:
        result = adapter(input_path, word_count)
        if not isinstance(result, ToolResult):
            raise TypeError(f"adapter {tool} returned {type(result)!r}, expected ToolResult")
    except Exception as exc:  # noqa: BLE001 — one tool must not abort the run
        result = _error_result(tool, version, exc)
        append_log(log_path, f"ERROR {tool}: {result.reason}")

    # Prefer adapter-declared version for cache key consistency when present
    if version is not None and result.version is None:
        result.version = version
    elif version is not None and result.version != version:
        # Keep result.version as source of truth for meta; still write what ran
        pass

    _write_cache(result, input_sha256)
    return result, False


def _stats_native(results: list[ToolResult]) -> dict[str, Any]:
    for r in results:
        if r.category == CATEGORY_STATS and r.status == ToolStatus.OK and isinstance(r.native, dict):
            return dict(r.native)
    return {}


def run_audit(input_path, force: bool = False) -> dict:
    """Coordinate env, stats, adapters, scoring, and reports.

    Skips a tool when ``raw/<tool>/meta.json`` matches input SHA-256 + tool
    version and status is OK, unless ``force`` is True.
    """
    path = Path(input_path)
    log_path = ROOT / "logs" / "run.log"
    append_log(log_path, f"BEGIN run_audit path={path} force={force}")

    environment: dict[str, Any] | None = None
    try:
        environment = inspect_environment()
        env_out = ROOT / "logs" / "environment.json"
        env_out.parent.mkdir(parents=True, exist_ok=True)
        env_out.write_text(
            json.dumps(environment, indent=2, sort_keys=True, default=str) + "\n",
            encoding="utf-8",
        )
    except Exception as exc:  # noqa: BLE001 — env is optional
        append_log(log_path, f"WARN env inspect failed: {type(exc).__name__}: {exc}")
        environment = {}

    stats = compute_input_stats(path)
    input_sha256 = stats.sha256
    word_count = stats.words

    results: list[ToolResult] = []
    skipped: list[str] = []
    ran: list[str] = []

    for adapter in get_adapters():
        result, was_skipped = _run_one(
            adapter, path, word_count, input_sha256, force, log_path
        )
        results.append(result)
        if was_skipped:
            skipped.append(result.tool)
        else:
            ran.append(result.tool)

    normalized_dir = ROOT / "normalized"
    normalized_dir.mkdir(parents=True, exist_ok=True)
    results_payload = {
        "input": {k: v for k, v in stats.to_dict().items() if k != "text"},
        "tools": [r.to_dict() for r in results],
        "skipped": skipped,
        "ran": ran,
        "force": force,
    }
    results_json = normalized_dir / "results.json"
    results_json.write_text(
        json.dumps(results_payload, indent=2, default=str) + "\n",
        encoding="utf-8",
    )

    slop = compute_slop_index(results)
    ai = compute_ai_likeness(results)
    stats_native = _stats_native(results)

    corroborated = corroborated_findings(results)

    report_paths = write_reports(
        out_dir=ROOT / "report",
        environment=environment,
        input_stats=stats,
        tool_results=results,
        slop=slop,
        ai=ai,
        stats_native=stats_native,
        corroborated=corroborated,
        false_positives=[],
    )

    append_log(
        log_path,
        f"END run_audit tools={len(results)} ran={len(ran)} skipped={len(skipped)}",
    )

    return {
        "input_stats": stats.to_dict(),
        "environment": environment,
        "tool_results": results,
        "results": results,
        "skipped": skipped,
        "ran": ran,
        "slop_index": slop,
        "ai_likeness": ai,
        "normalized_results": str(results_json),
        "report": report_paths,
    }
