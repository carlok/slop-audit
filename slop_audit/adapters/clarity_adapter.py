"""Adapter L: Clarity (roowus/clarity) — Binoculars family; local only."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from slop_audit.adapters.base import ROOT, run_cmd, write_raw
from slop_audit.adapters.ml_common import (
    MEM_CLARITY_BINOCULARS,
    MEM_CLARITY_FAST,
    clamp01,
    make_result,
    memory_gate,
    probe_import,
    venv_python,
)
from slop_audit.models import ToolStatus

TOOL = "clarity"
VERSION = "0.2.0"
_ENV = "ml-clarity"
_BIN = ROOT / "envs" / _ENV / "bin" / "clarity"
_PY = venv_python(_ENV)

NOTES_BASE = (
    "Clarity Binoculars-style score: lower = more AI-like. "
    "Labels: score < threshold_low → ai; score > threshold_high → human; else uncertain "
    "(defaults binoculars low=0.905 high=1.11; fast mode uses FAST_THRESHOLD_*). "
    "AI-likeness mapped linearly so score=low → 100, score=high → 0 "
    "(clamp 0–100). Local HF causal LMs only; never hosted detection APIs."
)


def map_clarity_score(
    doc_score: float, threshold_low: float, threshold_high: float
) -> float:
    """Invert/scale Clarity score to 0–100 AI-likeness (higher = more AI-like)."""
    if threshold_high == threshold_low:
        return 50.0
    # low → 100, high → 0
    return clamp01(100.0 * (threshold_high - float(doc_score)) / (threshold_high - threshold_low))


def parse_stdout(stdout: str) -> dict[str, Any]:
    data = json.loads(stdout)
    thr = data.get("thresholds") or {}
    low = float(thr.get("low"))
    high = float(thr.get("high"))
    doc_score = float(data["doc_score"])
    score = map_clarity_score(doc_score, low, high)
    sentences = data.get("sentences") or []
    ai_sents = sum(1 for s in sentences if s.get("label") == "ai")
    return {
        "native": data,
        "normalized_score": score,
        "findings_count": ai_sents,
        "errors": 0,
        "warnings": ai_sents,
        "info": sum(1 for s in sentences if s.get("label") == "uncertain"),
    }


def _choose_mode() -> tuple[str | None, str]:
    """Prefer binoculars mode; fall back to fast if RAM tight."""
    reason = memory_gate(MEM_CLARITY_BINOCULARS, "clarity binoculars (2×1.5B)")
    if reason is None:
        return "binoculars", ""
    fast_reason = memory_gate(MEM_CLARITY_FAST, "clarity fast (1×1.5B)")
    if fast_reason is not None:
        return None, f"{reason}; also {fast_reason}"
    return "fast", f"using fast mode (binoculars skipped: {reason})"


def run(input_path: Path, word_count: int) -> Any:
    del word_count
    path = Path(input_path)
    commands: list[str] = [str(_BIN), "--json", str(path)]

    if not _PY.is_file():
        return make_result(
            tool=TOOL,
            status=ToolStatus.NOT_RUN,
            version=VERSION,
            commands=commands,
            reason=f"missing venv python: {_PY}",
            notes=NOTES_BASE,
        )
    if not _BIN.is_file():
        return make_result(
            tool=TOOL,
            status=ToolStatus.NOT_RUN,
            version=VERSION,
            commands=commands,
            reason=f"missing binary: {_BIN}",
            notes=NOTES_BASE,
        )

    ok, detail = probe_import(
        _PY, "import clarity; import importlib.metadata as m; print(m.version('clarity'))"
    )
    if not ok:
        return make_result(
            tool=TOOL,
            status=ToolStatus.NOT_RUN,
            version=VERSION,
            commands=commands,
            reason=f"clarity import failed: {detail}",
            notes=NOTES_BASE,
        )
    version = detail.splitlines()[-1].strip() or VERSION

    mode, mode_note = _choose_mode()
    if mode is None:
        return make_result(
            tool=TOOL,
            status=ToolStatus.NOT_RUN,
            version=version,
            commands=commands,
            reason=mode_note,
            notes=NOTES_BASE,
        )

    commands = [str(_BIN), "--json", "--mode", mode, str(path)]
    env = {
        **os.environ,
        "HF_HUB_DISABLE_TELEMETRY": "1",
        "TRANSFORMERS_NO_ADVISORY_WARNINGS": "1",
    }
    proc = run_cmd(commands, timeout=1200, env=env)
    write_raw(TOOL, "stdout.txt", proc["stdout"])
    write_raw(TOOL, "stderr.txt", proc["stderr"])
    write_raw(TOOL, "returncode.txt", str(proc["returncode"]))

    stdout = (proc["stdout"] or "").strip()
    if not stdout:
        # OOM / model pull failure → record exact reason
        err = (proc["stderr"] or "")[:500]
        status = ToolStatus.NOT_RUN if "memory" in err.lower() or "killed" in err.lower() else ToolStatus.ERROR
        reason_prefix = "OOM/resource" if status == ToolStatus.NOT_RUN else "empty stdout"
        return make_result(
            tool=TOOL,
            status=status,
            version=version,
            commands=commands,
            native={"returncode": proc["returncode"]},
            reason=f"{reason_prefix} (rc={proc['returncode']}): {err}",
            notes=NOTES_BASE + (f" {mode_note}" if mode_note else f" mode={mode}"),
        )

    try:
        parsed = parse_stdout(stdout)
    except (json.JSONDecodeError, TypeError, ValueError, KeyError) as e:
        return make_result(
            tool=TOOL,
            status=ToolStatus.ERROR,
            version=version,
            commands=commands,
            reason=f"parse error: {type(e).__name__}: {e}",
            notes=NOTES_BASE,
        )

    write_raw(TOOL, "result.json", json.dumps(parsed["native"], indent=2) + "\n")
    notes = NOTES_BASE + f" mode={mode}."
    if mode_note:
        notes += " " + mode_note
    if parsed["native"].get("mode") == "fast" or mode == "fast":
        notes += " Lightweight/fast mode labeled (experimental calibration)."
    return make_result(
        tool=TOOL,
        status=ToolStatus.OK,
        version=version,
        commands=commands,
        native=parsed["native"],
        normalized_score=parsed["normalized_score"],
        findings_count=parsed["findings_count"],
        errors=parsed["errors"],
        warnings=parsed["warnings"],
        info=parsed["info"],
        notes=notes,
    )


run.tool = TOOL  # type: ignore[attr-defined]
run.version = VERSION  # type: ignore[attr-defined]
