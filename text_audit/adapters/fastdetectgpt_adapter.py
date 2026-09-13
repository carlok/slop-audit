"""Adapter N: Fast-DetectGPT (junchaoIU) — published local_infer path; local only."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from text_audit.adapters.base import ROOT, run_cmd, write_raw
from text_audit.adapters.ml_common import (
    MEM_FASTDETECT_DEFAULT,
    clamp01,
    make_result,
    memory_gate,
    probe_import,
    venv_python,
)
from text_audit.models import ToolStatus

TOOL = "fastdetectgpt"
VERSION = "local_infer"
_ENV = "ml-fastdetect"
_PY = venv_python(_ENV)
_CLONE = ROOT / "envs" / "src" / "ml-fastdetect"
_SCRIPTS = _CLONE / "scripts"
_REF = _CLONE / "local_infer_ref"

# Published defaults from scripts/local_infer.py:
# reference=gpt-j-6B, scoring=gpt-neo-2.7B; ProbEstimator → P(fake).
NOTES_BASE = (
    "Fast-DetectGPT analytic sampling discrepancy → ProbEstimator P(fake). "
    "Published path: reference=gpt-j-6B, scoring=gpt-neo-2.7B, refs in local_infer_ref/. "
    "AI-likeness = probability_fake × 100 (0–100). Decision boundary often ~50% fake. "
    "Local models only; openai package excluded at install (no hosted APIs)."
)

_WORKER = r"""
import json, os, sys
from pathlib import Path
import argparse
import glob
import numpy as np
import torch

clone = Path(sys.argv[1])
text_path = Path(sys.argv[2])
text = text_path.read_text(encoding="utf-8")
sys.path.insert(0, str(clone / "scripts"))
os.chdir(clone)

from model import load_tokenizer, load_model
from fast_detect_gpt import get_sampling_discrepancy_analytic

class ProbEstimator:
    def __init__(self, ref_path):
        self.real_crits = []
        self.fake_crits = []
        for result_file in glob.glob(os.path.join(ref_path, "*.json")):
            with open(result_file, "r") as fin:
                res = json.load(fin)
                self.real_crits.extend(res["predictions"]["real"])
                self.fake_crits.extend(res["predictions"]["samples"])
    def crit_to_prob(self, crit):
        offset = np.sort(np.abs(np.array(self.real_crits + self.fake_crits) - crit))[100]
        cnt_real = np.sum(
            (np.array(self.real_crits) > crit - offset)
            & (np.array(self.real_crits) < crit + offset)
        )
        cnt_fake = np.sum(
            (np.array(self.fake_crits) > crit - offset)
            & (np.array(self.fake_crits) < crit + offset)
        )
        return float(cnt_fake / (cnt_real + cnt_fake))

ref_name = "gpt-j-6B"
score_name = "gpt-neo-2.7B"
device = "cpu"
cache_dir = str(clone / "cache")
os.makedirs(cache_dir, exist_ok=True)

scoring_tokenizer = load_tokenizer(score_name, "xsum", cache_dir)
scoring_model = load_model(score_name, device, cache_dir)
scoring_model.eval()
reference_tokenizer = load_tokenizer(ref_name, "xsum", cache_dir)
reference_model = load_model(ref_name, device, cache_dir)
reference_model.eval()
criterion_fn = get_sampling_discrepancy_analytic
prob_estimator = ProbEstimator(str(clone / "local_infer_ref"))

tokenized = scoring_tokenizer(
    text, return_tensors="pt", padding=True, return_token_type_ids=False
).to(device)
labels = tokenized.input_ids[:, 1:]
with torch.no_grad():
    logits_score = scoring_model(**tokenized).logits[:, :-1]
    tokenized_ref = reference_tokenizer(
        text, return_tensors="pt", padding=True, return_token_type_ids=False
    ).to(device)
    logits_ref = reference_model(**tokenized_ref).logits[:, :-1]
    crit = criterion_fn(logits_ref, logits_score, labels)
prob = float(prob_estimator.crit_to_prob(crit))
out = {
    "criterion": float(crit) if not hasattr(crit, "item") else float(crit),
    "probability_fake": prob,
    "ai_probability": prob,
    "reference_model": ref_name,
    "scoring_model": score_name,
    "device": device,
}
# crit may be tensor
if hasattr(crit, "item"):
    out["criterion"] = float(crit.item())
print(json.dumps(out))
"""


def map_fastdetect_score(probability_fake: float) -> float:
    """Map P(fake) in [0,1] to 0–100 AI-likeness."""
    return clamp01(float(probability_fake) * 100.0)


def parse_native(data: dict[str, Any]) -> dict[str, Any]:
    prob = data.get("probability_fake")
    if prob is None:
        prob = data.get("ai_probability")
    if prob is None:
        raise KeyError("probability_fake")
    score = map_fastdetect_score(float(prob))
    return {
        "native": data,
        "normalized_score": score,
        "findings_count": 1 if score >= 50 else 0,
        "errors": 0,
        "warnings": 1 if score >= 50 else 0,
        "info": 0,
    }


def run(input_path: Path, word_count: int) -> Any:
    del word_count
    path = Path(input_path)
    commands = [str(_PY), "-c", "<fastdetect_worker>", str(_CLONE), str(path)]

    if not _PY.is_file():
        return make_result(
            tool=TOOL,
            status=ToolStatus.NOT_RUN,
            version=VERSION,
            commands=commands,
            reason=f"missing venv python: {_PY}",
            notes=NOTES_BASE,
        )
    if not _CLONE.is_dir() or not _SCRIPTS.is_dir():
        return make_result(
            tool=TOOL,
            status=ToolStatus.NOT_RUN,
            version=VERSION,
            commands=commands,
            reason=f"missing fast-detectgpt clone/scripts: {_CLONE}",
            notes=NOTES_BASE,
        )
    if not _REF.is_dir():
        return make_result(
            tool=TOOL,
            status=ToolStatus.NOT_RUN,
            version=VERSION,
            commands=commands,
            reason=f"missing local_infer_ref: {_REF}",
            notes=NOTES_BASE,
        )

    ok, detail = probe_import(_PY, "import torch, transformers; print('ok')")
    if not ok:
        return make_result(
            tool=TOOL,
            status=ToolStatus.NOT_RUN,
            version=VERSION,
            commands=commands,
            reason=f"torch/transformers import failed: {detail}",
            notes=NOTES_BASE,
        )

    mem_reason = memory_gate(
        MEM_FASTDETECT_DEFAULT, "Fast-DetectGPT gpt-j-6B + gpt-neo-2.7B"
    )
    if mem_reason is not None:
        return make_result(
            tool=TOOL,
            status=ToolStatus.NOT_RUN,
            version=VERSION,
            commands=commands,
            reason=mem_reason,
            notes=NOTES_BASE,
        )

    commands = [str(_PY), "-c", _WORKER, str(_CLONE), str(path)]
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
            commands=[str(_PY), "-c", "<fastdetect_worker>", str(_CLONE), str(path)],
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
            commands=[str(_PY), "-c", "<fastdetect_worker>", str(_CLONE), str(path)],
            reason=f"parse error: {type(e).__name__}: {e}",
            notes=NOTES_BASE,
        )

    write_raw(TOOL, "result.json", json.dumps(parsed["native"], indent=2) + "\n")
    return make_result(
        tool=TOOL,
        status=ToolStatus.OK,
        version=VERSION,
        commands=[str(_PY), "-c", "<fastdetect_worker>", str(_CLONE), str(path)],
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
