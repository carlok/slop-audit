"""Unit (+ gated integration) tests for ML authorship adapters K–N."""
from __future__ import annotations

import json
from contextlib import ExitStack
from pathlib import Path
from unittest import mock

import pytest

from slop_audit.adapters import get_adapters
from slop_audit.adapters.base import ROOT
from slop_audit.models import CATEGORY_AI, ToolStatus
from slop_audit.scoring_ai import TOOL_FAMILY

FIX = ROOT / "tests" / "fixtures" / "short.txt"


def _fake_installed_path() -> mock.MagicMock:
    """Path stand-in so adapters pass venv/binary existence checks in unit tests."""
    p = mock.MagicMock()
    p.is_file.return_value = True
    p.is_dir.return_value = True
    return p

AI_DETECT_JSON = """\
{
  "model_ai_pct": 72.5,
  "ai_count": 2,
  "human_count": 1,
  "skipped_count": 0,
  "model": "desklib/ai-text-detector-v1.01 (DeBERTa-v3-large)",
  "sentences": []
}
"""

CLARITY_JSON = """\
{
  "doc_score": 0.95,
  "doc_label": "uncertain",
  "reliable": true,
  "truncated": false,
  "n_tokens": 120,
  "mode": "binoculars",
  "thresholds": {"low": 0.905, "high": 1.11},
  "sentences": [
    {"label": "ai", "score": 0.8, "text": "x"},
    {"label": "human", "score": 1.2, "text": "y"},
    {"label": "uncertain", "score": 1.0, "text": "z"}
  ]
}
"""


def test_registry_includes_ml_tools():
    names = [getattr(a, "tool", a.__name__) for a in get_adapters()]
    for t in ("ai_detect", "clarity", "binoculars", "fastdetectgpt"):
        assert t in names
        assert t in TOOL_FAMILY


def test_parse_ai_detect_uses_model_ai_pct():
    from slop_audit.adapters.ai_detect import map_ai_detect_score, parse_stdout

    parsed = parse_stdout(AI_DETECT_JSON)
    assert parsed["normalized_score"] == pytest.approx(72.5)
    assert parsed["findings_count"] == 2
    assert parsed["warnings"] == 2
    assert map_ai_detect_score(json.loads(AI_DETECT_JSON)) == pytest.approx(72.5)


def test_map_clarity_score_threshold_semantics():
    from slop_audit.adapters.clarity_adapter import map_clarity_score, parse_stdout

    assert map_clarity_score(0.905, 0.905, 1.11) == pytest.approx(100.0)
    assert map_clarity_score(1.11, 0.905, 1.11) == pytest.approx(0.0)
    mid = (0.905 + 1.11) / 2
    assert map_clarity_score(mid, 0.905, 1.11) == pytest.approx(50.0)
    parsed = parse_stdout(CLARITY_JSON)
    expected = 100.0 * (1.11 - 0.95) / (1.11 - 0.905)
    assert parsed["normalized_score"] == pytest.approx(expected)
    assert parsed["findings_count"] == 1
    assert parsed["info"] == 1


def test_map_binoculars_score_boundary_at_threshold():
    from slop_audit.adapters.binoculars_adapter import map_binoculars_score, parse_native

    thr = 0.8536432310785527
    assert map_binoculars_score(thr, thr) == pytest.approx(50.0)
    assert map_binoculars_score(0.0, thr) == pytest.approx(100.0)
    assert map_binoculars_score(2 * thr, thr) == pytest.approx(0.0)
    parsed = parse_native(
        {"score": 0.7, "threshold": thr, "prediction": "Most likely AI-generated"}
    )
    assert parsed["normalized_score"] > 50
    assert parsed["warnings"] == 1


def test_map_fastdetect_probability():
    from slop_audit.adapters.fastdetectgpt_adapter import (
        map_fastdetect_score,
        parse_native,
    )

    assert map_fastdetect_score(0.87) == pytest.approx(87.0)
    assert map_fastdetect_score(0.0) == pytest.approx(0.0)
    parsed = parse_native({"probability_fake": 0.42, "criterion": 1.2})
    assert parsed["normalized_score"] == pytest.approx(42.0)
    assert parsed["findings_count"] == 0


def test_memory_gate_reports_reason():
    from slop_audit.adapters import ml_common

    with mock.patch.object(ml_common, "mem_available_bytes", return_value=100):
        reason = ml_common.memory_gate(ml_common.GIB, "test-tool")
    assert reason is not None
    assert "insufficient memory" in reason
    assert "test-tool" in reason


def test_category_ai_authorship_on_missing_venv():
    from slop_audit.adapters import ai_detect as ad

    with mock.patch.object(ad, "_PY", Path("/nonexistent/python")):
        with mock.patch.object(ad, "_BIN", Path("/nonexistent/ai-detect")):
            r = ad.run(FIX, word_count=10)
    assert r.status == ToolStatus.NOT_RUN
    assert r.category == CATEGORY_AI
    assert r.tool == "ai_detect"
    assert r.normalized_score is None
    assert "missing" in r.reason.lower()


@pytest.mark.parametrize(
    "mod_name,tool",
    [
        ("slop_audit.adapters.binoculars_adapter", "binoculars"),
        ("slop_audit.adapters.fastdetectgpt_adapter", "fastdetectgpt"),
    ],
)
def test_heavy_adapters_not_run_when_mem_low(mod_name, tool):
    import importlib

    mod = importlib.import_module(mod_name)
    fake = _fake_installed_path()
    with ExitStack() as stack:
        stack.enter_context(mock.patch.object(mod, "_PY", fake))
        stack.enter_context(
            mock.patch.object(mod, "probe_import", return_value=(True, "ok"))
        )
        stack.enter_context(
            mock.patch.object(
                mod, "memory_gate", return_value="insufficient memory for mock"
            )
        )
        stack.enter_context(mock.patch.object(mod, "_CLONE", fake))
        if tool == "fastdetectgpt":
            stack.enter_context(mock.patch.object(mod, "_SCRIPTS", fake))
            stack.enter_context(mock.patch.object(mod, "_REF", fake))
        r = mod.run(FIX, word_count=10)
    assert r.tool == tool
    assert r.category == CATEGORY_AI
    assert r.status == ToolStatus.NOT_RUN
    assert r.normalized_score is None
    assert "memory" in r.reason.lower()


def test_ai_detect_mocked_ok_path():
    from slop_audit.adapters import ai_detect as ad

    fake_proc = {
        "returncode": 0,
        "stdout": AI_DETECT_JSON,
        "stderr": "",
    }
    fake = _fake_installed_path()
    with mock.patch.object(ad, "_PY", fake), mock.patch.object(ad, "_BIN", fake):
        with mock.patch.object(ad, "probe_import", return_value=(True, "1.0.0")):
            with mock.patch.object(ad, "_choose_model", return_value=("desklib", "")):
                with mock.patch.object(ad, "run_cmd", return_value=fake_proc):
                    with mock.patch.object(ad, "write_raw"):
                        r = ad.run(FIX, word_count=10)
    assert r.status == ToolStatus.OK
    assert r.category == CATEGORY_AI
    assert r.normalized_score == pytest.approx(72.5)
    assert "LIKELY AI" in r.notes or "model_ai_pct" in r.notes


def test_clarity_mocked_ok_path():
    from slop_audit.adapters import clarity_adapter as ca

    fake_proc = {"returncode": 0, "stdout": CLARITY_JSON, "stderr": ""}
    fake = _fake_installed_path()
    with mock.patch.object(ca, "_PY", fake), mock.patch.object(ca, "_BIN", fake):
        with mock.patch.object(ca, "probe_import", return_value=(True, "0.2.0")):
            with mock.patch.object(ca, "_choose_mode", return_value=("binoculars", "")):
                with mock.patch.object(ca, "run_cmd", return_value=fake_proc):
                    with mock.patch.object(ca, "write_raw"):
                        r = ca.run(FIX, word_count=10)
    assert r.status == ToolStatus.OK
    assert r.category == CATEGORY_AI
    assert 0.0 <= r.normalized_score <= 100.0
    assert "threshold" in r.notes.lower()


def test_live_memory_gates_heavy_tools():
    """Live: Falcon / gpt-j pair must NOT_RUN when MemAvailable is below budgets.

    Soft-skips when host RAM is high enough that the tools might actually run;
    mocked gate tests remain the portable contract guarantee.
    """
    import pytest

    from slop_audit.adapters import binoculars_adapter, fastdetectgpt_adapter
    from slop_audit.adapters.ml_common import (
        MEM_BINOCULARS_FALCON,
        MEM_FASTDETECT_DEFAULT,
        mem_available_bytes,
    )

    avail = mem_available_bytes()
    # Skip only when BOTH heavy tools could clear their memory gates.
    if avail >= min(MEM_BINOCULARS_FALCON, MEM_FASTDETECT_DEFAULT):
        pytest.skip(
            f"MemAvailable={avail} >= heavy-tool budgets; "
            "live NOT_RUN assertion not portable (mocked gates cover contract)"
        )

    for adapter in (binoculars_adapter, fastdetectgpt_adapter):
        r = adapter.run(FIX, word_count=10)
        assert r.category == CATEGORY_AI
        assert r.status == ToolStatus.NOT_RUN
        assert r.normalized_score is None
        assert r.reason
        # Prefer memory reason when venv/clone present
        assert any(
            k in r.reason
            for k in ("MemAvailable", "insufficient memory", "missing")
        )
