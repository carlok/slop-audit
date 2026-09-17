"""Shared helpers for best-effort local ML authorship adapters."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from slop_audit.adapters.base import ROOT, run_cmd
from slop_audit.models import CATEGORY_AI, ToolResult, ToolStatus

GIB = 1024**3

# Rough MemAvailable budgets before launching heavy local inference.
MEM_AI_DETECT_DESKLIB = int(8.0 * GIB)  # DeBERTa-v3-large + torch headroom
MEM_AI_DETECT_LIGHT = int(1.5 * GIB)
MEM_CLARITY_BINOCULARS = int(8.0 * GIB)  # Qwen2.5-1.5B × 2 fp32
MEM_CLARITY_FAST = int(4.5 * GIB)  # single 1.5B fp32
MEM_BINOCULARS_FALCON = int(20.0 * GIB)  # Falcon-7B × 2 (published pair)
MEM_FASTDETECT_DEFAULT = int(14.0 * GIB)  # gpt-j-6B + gpt-neo-2.7B


def mem_available_bytes() -> int:
    try:
        with open("/proc/meminfo", encoding="utf-8") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        pass
    return 0


def memory_gate(need_bytes: int, what: str) -> str | None:
    """Return NOT_RUN reason if MemAvailable < need_bytes; else None."""
    avail = mem_available_bytes()
    if avail < need_bytes:
        return (
            f"insufficient memory for {what}: "
            f"MemAvailable={avail} < need={need_bytes} "
            f"({need_bytes / GIB:.1f} GiB)"
        )
    return None


def venv_python(env_name: str) -> Path:
    return ROOT / "envs" / env_name / "bin" / "python"


def probe_import(python: Path, code: str, timeout: float = 60) -> tuple[bool, str]:
    """Run a short import probe in ``python``. Returns (ok, detail)."""
    if not python.is_file():
        return False, f"missing venv python: {python}"
    proc = run_cmd([str(python), "-c", code], timeout=timeout)
    if proc["returncode"] == 0:
        return True, (proc["stdout"] or "").strip() or "ok"
    err = (proc["stderr"] or proc["stdout"] or "").strip()
    return False, err[:500] or f"import probe rc={proc['returncode']}"


def make_result(
    *,
    tool: str,
    status: ToolStatus,
    version: str | None,
    commands: list[str],
    native: Any = None,
    normalized_score: float | None = None,
    findings_count: int = 0,
    errors: int = 0,
    warnings: int = 0,
    info: int = 0,
    reason: str = "",
    notes: str = "",
) -> ToolResult:
    return ToolResult(
        tool=tool,
        status=status,
        version=version,
        category=CATEGORY_AI,
        commands=commands,
        raw_dir=f"raw/{tool}",
        native=native,
        normalized_score=normalized_score,
        findings_count=findings_count,
        errors=errors,
        warnings=warnings,
        info=info,
        reason=reason,
        notes=notes,
    )


def clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else 100.0 if x > 100.0 else x
