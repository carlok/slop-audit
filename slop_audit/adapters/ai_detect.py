"""Adapter K: ai-detect (houtini-ai) — DeBERTa family; local only."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from slop_audit.adapters.base import ROOT, run_cmd, write_raw
from slop_audit.adapters.ml_common import (
    MEM_AI_DETECT_DESKLIB,
    MEM_AI_DETECT_LIGHT,
    make_result,
    memory_gate,
    probe_import,
    venv_python,
)
from slop_audit.models import ToolStatus

TOOL = "ai_detect"
VERSION = "1.0.0"
_ENV = "ml-aidetect"
_BIN = ROOT / "envs" / _ENV / "bin" / "ai-detect"
_PY = venv_python(_ENV)

# Verdict thresholds from ai_detect.detector.verdict (model_ai_pct):
# >50 LIKELY AI, <40 LIKELY HUMAN, else MIXED.
NOTES_BASE = (
    "AI-likeness = model_ai_pct (mean sentence P(AI)×100). "
    "Thresholds: >50 LIKELY AI, <40 LIKELY HUMAN, else MIXED "
    "(ai_detect.detector.verdict). Sentence label AI if ai_prob>=0.5. "
    "Local weights only; never hosted detection APIs."
)


def map_ai_detect_score(native: dict[str, Any]) -> float:
    """Map native report to 0–100 AI-likeness (higher = more AI-like)."""
    pct = native.get("model_ai_pct")
    if pct is None:
        raise KeyError("model_ai_pct")
    return float(pct)


def parse_stdout(stdout: str) -> dict[str, Any]:
    data = json.loads(stdout)
    score = map_ai_detect_score(data)
    ai_count = int(data.get("ai_count") or 0)
    return {
        "native": data,
        "normalized_score": score,
        "findings_count": ai_count,
        "errors": 0,
        "warnings": ai_count,
        "info": int(data.get("human_count") or 0),
    }


def _choose_model() -> tuple[str | None, str]:
    """Prefer desklib (DeBERTa); fall back to light ONNX if RAM/deps force it."""
    reason = memory_gate(MEM_AI_DETECT_DESKLIB, "ai-detect desklib/DeBERTa")
    if reason is None:
        return "desklib", ""
    # light fallback
    light_mem = memory_gate(MEM_AI_DETECT_LIGHT, "ai-detect light ONNX")
    if light_mem is not None:
        return None, f"{reason}; also {light_mem}"
    ok, detail = probe_import(_PY, "import onnxruntime")
    if not ok:
        return None, (
            f"{reason}; light fallback unavailable "
            f"(onnxruntime import failed: {detail})"
        )
    return "light", (
        f"using light ONNX model (desklib skipped: {reason})"
    )


def run(input_path: Path, word_count: int) -> Any:
    del word_count  # unused; score is native AI %
    path = Path(input_path)
    commands: list[str] = [str(_BIN), "--json", "--file", str(path), "--device", "cpu"]

    if not _PY.is_file():
        return make_result(
            tool=TOOL,
            status=ToolStatus.NOT_RUN,
            version=VERSION,
            commands=commands,
            reason=f"missing venv python: {_PY}",
        )
    if not _BIN.is_file():
        return make_result(
            tool=TOOL,
            status=ToolStatus.NOT_RUN,
            version=VERSION,
            commands=commands,
            reason=f"missing binary: {_BIN}",
        )

    ok, detail = probe_import(_PY, "import ai_detect; print(ai_detect.__version__)")
    if not ok:
        return make_result(
            tool=TOOL,
            status=ToolStatus.NOT_RUN,
            version=VERSION,
            commands=commands,
            reason=f"ai_detect import failed: {detail}",
        )
    version = detail.splitlines()[-1].strip() or VERSION

    model, model_note = _choose_model()
    if model is None:
        return make_result(
            tool=TOOL,
            status=ToolStatus.NOT_RUN,
            version=version,
            commands=commands,
            reason=model_note,
            notes=NOTES_BASE,
        )

    commands = [
        str(_BIN),
        "--json",
        "--file",
        str(path),
        "--model",
        model,
        "--device",
        "cpu",
    ]
    # Prefer local cache; allow HF weight download (not text APIs).
    env = {
        **{k: v for k, v in __import__("os").environ.items()},
        "HF_HUB_DISABLE_TELEMETRY": "1",
        "TRANSFORMERS_NO_ADVISORY_WARNINGS": "1",
    }
    proc = run_cmd(commands, timeout=900, env=env)
    write_raw(TOOL, "stdout.txt", proc["stdout"])
    write_raw(TOOL, "stderr.txt", proc["stderr"])
    write_raw(TOOL, "returncode.txt", str(proc["returncode"]))

    stdout = (proc["stdout"] or "").strip()
    # Model load chatter may go to stderr; JSON is on stdout.
    if not stdout:
        return make_result(
            tool=TOOL,
            status=ToolStatus.ERROR,
            version=version,
            commands=commands,
            native={"returncode": proc["returncode"]},
            reason=(
                f"empty stdout (rc={proc['returncode']}): "
                f"{(proc['stderr'] or '')[:400]}"
            ),
            notes=NOTES_BASE + (f" {model_note}" if model_note else ""),
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
    notes = NOTES_BASE + f" model={model}."
    if model_note:
        notes += " " + model_note
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
