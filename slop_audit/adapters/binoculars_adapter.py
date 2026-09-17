"""Adapter M: Binoculars (ahans30) — published Falcon-7B pair; local only."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from slop_audit.adapters.base import ROOT, run_cmd, write_raw
from slop_audit.adapters.ml_common import (
    MEM_BINOCULARS_FALCON,
    clamp01,
    make_result,
    memory_gate,
    probe_import,
    venv_python,
)
from slop_audit.models import ToolStatus

TOOL = "binoculars"
VERSION = "0.0.10"
_ENV = "ml-binoculars"
_PY = venv_python(_ENV)
_CLONE = ROOT / "envs" / "src" / "ml-binoculars"

# Published thresholds (Falcon-7B / Falcon-7B-Instruct), from binoculars.detector:
# low-fpr (default): 0.8536…; accuracy: 0.9015…
# predict: score < threshold → "Most likely AI-generated"
NOTES_BASE = (
    "Binoculars score = perplexity/cross-perplexity; lower = more AI-like. "
    "Default mode low-fpr threshold≈0.8536 (FPR~0.01%); accuracy mode≈0.9015. "
    "Native predict: score < threshold → Most likely AI-generated. "
    "AI-likeness: 50 + 50*(threshold-score)/threshold, clamp 0–100 "
    "(boundary score=threshold → 50). Published Falcon-7B pair only; "
    "no arbitrary model substitution. Local weights only."
)

_WORKER = r"""
import json, sys
from pathlib import Path
text = Path(sys.argv[1]).read_text(encoding="utf-8")
from binoculars import Binoculars
from binoculars.detector import (
    BINOCULARS_ACCURACY_THRESHOLD,
    BINOCULARS_FPR_THRESHOLD,
)
# CPU: float32 (bfloat16 often unsupported / slow on CPU)
bino = Binoculars(use_bfloat16=False, mode="low-fpr")
score = float(bino.compute_score(text))
pred = bino.predict(text)
out = {
    "score": score,
    "prediction": pred if isinstance(pred, str) else pred,
    "threshold": float(bino.threshold),
    "mode": "low-fpr",
    "thresholds": {
        "low-fpr": float(BINOCULARS_FPR_THRESHOLD),
        "accuracy": float(BINOCULARS_ACCURACY_THRESHOLD),
    },
    "observer": "tiiuae/falcon-7b",
    "performer": "tiiuae/falcon-7b-instruct",
}
print(json.dumps(out))
"""


def map_binoculars_score(score: float, threshold: float) -> float:
    """Map Binoculars score to 0–100 AI-likeness (higher = more AI-like)."""
    thr = float(threshold)
    if thr <= 0:
        return 50.0
    # score=0 → 100; score=threshold → 50; score=2*threshold → 0
    return clamp01(50.0 + 50.0 * (thr - float(score)) / thr)


def parse_native(data: dict[str, Any]) -> dict[str, Any]:
    score = float(data["score"])
    thr = float(data["threshold"])
    pred = data.get("prediction") or ""
    ai_like = "AI" in str(pred)
    return {
        "native": data,
        "normalized_score": map_binoculars_score(score, thr),
        "findings_count": 1 if ai_like else 0,
        "errors": 0,
        "warnings": 1 if ai_like else 0,
        "info": 0,
    }


def run(input_path: Path, word_count: int) -> Any:
    del word_count
    path = Path(input_path)
    commands = [str(_PY), "-c", "<binoculars_worker>", str(path)]

    if not _PY.is_file():
        return make_result(
            tool=TOOL,
            status=ToolStatus.NOT_RUN,
            version=VERSION,
            commands=commands,
            reason=f"missing venv python: {_PY}",
            notes=NOTES_BASE,
        )
    if not _CLONE.is_dir():
        return make_result(
            tool=TOOL,
            status=ToolStatus.NOT_RUN,
            version=VERSION,
            commands=commands,
            reason=f"missing Binoculars clone: {_CLONE}",
            notes=NOTES_BASE,
        )

    ok, detail = probe_import(_PY, "from binoculars import Binoculars; print('ok')")
    if not ok:
        return make_result(
            tool=TOOL,
            status=ToolStatus.NOT_RUN,
            version=VERSION,
            commands=commands,
            reason=f"binoculars import failed: {detail}",
            notes=NOTES_BASE,
        )

    mem_reason = memory_gate(MEM_BINOCULARS_FALCON, "Binoculars Falcon-7B×2")
    if mem_reason is not None:
        return make_result(
            tool=TOOL,
            status=ToolStatus.NOT_RUN,
            version=VERSION,
            commands=commands,
            reason=mem_reason,
            notes=NOTES_BASE,
        )

    commands = [str(_PY), "-c", _WORKER, str(path)]
    env = {
        **os.environ,
        "HF_HUB_DISABLE_TELEMETRY": "1",
        "TRANSFORMERS_NO_ADVISORY_WARNINGS": "1",
    }
    proc = run_cmd(commands, timeout=1800, env=env)
    write_raw(TOOL, "stdout.txt", proc["stdout"])
    write_raw(TOOL, "stderr.txt", proc["stderr"])
    write_raw(TOOL, "returncode.txt", str(proc["returncode"]))

    stdout = (proc["stdout"] or "").strip()
    # Worker prints a single JSON object as the last non-empty line ideally;
    # take the last line that looks like JSON.
    json_line = ""
    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            json_line = line
            break
    if not json_line:
        err = (proc["stderr"] or "")[:500]
        low = err.lower()
        status = (
            ToolStatus.NOT_RUN
            if any(x in low for x in ("memory", "killed", "oom", "cannot allocate"))
            else ToolStatus.ERROR
        )
        return make_result(
            tool=TOOL,
            status=status,
            version=VERSION,
            commands=[str(_PY), "-c", "<binoculars_worker>", str(path)],
            native={"returncode": proc["returncode"]},
            reason=f"no JSON output (rc={proc['returncode']}): {err}",
            notes=NOTES_BASE,
        )

    try:
        data = json.loads(json_line)
        parsed = parse_native(data)
    except (json.JSONDecodeError, TypeError, ValueError, KeyError) as e:
        return make_result(
            tool=TOOL,
            status=ToolStatus.ERROR,
            version=VERSION,
            commands=[str(_PY), "-c", "<binoculars_worker>", str(path)],
            reason=f"parse error: {type(e).__name__}: {e}",
            notes=NOTES_BASE,
        )

    write_raw(TOOL, "result.json", json.dumps(parsed["native"], indent=2) + "\n")
    return make_result(
        tool=TOOL,
        status=ToolStatus.OK,
        version=VERSION,
        commands=[str(_PY), "-c", "<binoculars_worker>", str(path)],
        native=parsed["native"],
        normalized_score=parsed["normalized_score"],
        findings_count=parsed["findings_count"],
        errors=parsed["errors"],
        warnings=parsed["warnings"],
        info=parsed["info"],
        notes=NOTES_BASE,
    )


run.tool = TOOL  # type: ignore[attr-defined]
run.version = VERSION  # type: ignore[attr-defined]
