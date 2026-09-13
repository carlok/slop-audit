"""Restartability: second run skips OK tools when sha+version match."""
from __future__ import annotations

import json
from pathlib import Path

from text_audit.models import CATEGORY_SLOP, ToolResult, ToolStatus


def _make_fake(tool: str = "fake_tool", version: str = "1.0.0"):
    calls = {"n": 0}

    def fake_adapter(input_path: Path, word_count: int) -> ToolResult:
        calls["n"] += 1
        raw_dir = f"raw/{tool}"
        return ToolResult(
            tool=tool,
            status=ToolStatus.OK,
            version=version,
            category=CATEGORY_SLOP,
            commands=[f"fake-{tool}"],
            raw_dir=raw_dir,
            native={"score": 42.0, "calls": calls["n"]},
            normalized_score=42.0,
            findings_count=0,
            errors=0,
            warnings=0,
            info=0,
            reason="",
            notes="fake",
        )

    fake_adapter.tool = tool
    fake_adapter.version = version
    fake_adapter.calls = calls
    return fake_adapter


def test_second_run_skips_ok_tool(tmp_path, monkeypatch):
    from text_audit import runner

    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr("text_audit.adapters.base.ROOT", tmp_path)

    fake = _make_fake()
    monkeypatch.setattr(runner, "get_adapters", lambda: [fake])

    inp = tmp_path / "input" / "target.txt"
    inp.parent.mkdir(parents=True)
    inp.write_text(
        "Hello world. Second sentence for the audit pipeline.",
        encoding="utf-8",
    )

    out1 = runner.run_audit(inp, force=False)
    assert fake.calls["n"] == 1
    assert (tmp_path / "normalized" / "results.json").is_file()
    assert (tmp_path / "raw" / "fake_tool" / "meta.json").is_file()
    assert "tool_results" in out1 or "results" in out1

    out2 = runner.run_audit(inp, force=False)
    assert fake.calls["n"] == 1, "second run must skip OK cached tool"
    meta = json.loads((tmp_path / "raw" / "fake_tool" / "meta.json").read_text())
    assert meta["status"] == "OK"
    assert "sha256" in meta or "input_sha256" in meta

    runner.run_audit(inp, force=True)
    assert fake.calls["n"] == 2, "--force must re-run even when cache OK"
