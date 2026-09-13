import json
from pathlib import Path

from text_audit.models import ToolResult, ToolStatus, CATEGORY_SLOP, CATEGORY_AI
from text_audit.report import write_reports


def _ok(tool, score, category=CATEGORY_SLOP):
    return ToolResult(
        tool,
        ToolStatus.OK,
        "1.0",
        category,
        [f"{tool} --run"],
        f"raw/{tool}",
        {"score": score},
        score,
        0,
        0,
        0,
        0,
        "",
        "",
    )


def _minimal_args(tmp_path: Path):
    environment = {"os": "linux", "python": "3.13"}
    input_stats = {
        "path": "input/target.txt",
        "sha256": "abc",
        "bytes": 10,
        "characters": 10,
        "words": 2,
        "sentences": 1,
        "paragraphs": 1,
    }
    tool_results = [
        _ok("slopscore", 40),
        ToolResult(
            "dslop",
            ToolStatus.NOT_RUN,
            None,
            CATEGORY_SLOP,
            [],
            "raw/dslop",
            None,
            None,
            0,
            0,
            0,
            0,
            "missing",
            "",
        ),
        _ok("ai_detect", 70, CATEGORY_AI),
    ]
    slop = {
        "score": 40.0,
        "band": "MODERATE",
        "weights_used": {"slopscore": 1.0},
        "components": {"slopscore": 40.0},
    }
    ai = {
        "ensemble": 70.0,
        "agreement": "HIGH",
        "per_tool": {"ai_detect": 70.0},
        "families_used": {"deberta": 1.0},
    }
    stats_native = {"flesch_reading_ease": 60.0, "ttr": 0.5}
    corroborated = [{"phenomenon": "hedging", "tools": ["slopscore"], "count": 1}]
    false_positives = [{"item": "em dash", "note": "typography alone is weak"}]
    return dict(
        out_dir=tmp_path,
        environment=environment,
        input_stats=input_stats,
        tool_results=tool_results,
        slop=slop,
        ai=ai,
        stats_native=stats_native,
        corroborated=corroborated,
        false_positives=false_positives,
    )


def test_write_reports_slop_index_in_md_and_json(tmp_path):
    paths = write_reports(**_minimal_args(tmp_path))
    md_path = Path(paths["md"])
    json_path = Path(paths["json"])
    assert md_path.name == "report.md"
    assert json_path.name == "report.json"
    md = md_path.read_text(encoding="utf-8")
    assert "Slop Index:" in md
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert "slop_index" in data


def test_write_reports_has_design_sections_and_deferred_human(tmp_path):
    paths = write_reports(**_minimal_args(tmp_path))
    md = Path(paths["md"]).read_text(encoding="utf-8")
    for heading in (
        "Executive",
        "Environment",
        "Input",
        "Tool matrix",
        "Slop",
        "Statistical",
        "AI-authorship",
        "Corroborated",
        "False positives",
        "Final assessment",
    ):
        assert heading in md
    assert "deferred until real user text" in md
    # Epistemic: never claim authorship as written by AI
    assert "written by AI" not in md.lower()
    data = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
    assert "ai_likeness" in data
    assert data["slop_index"]["score"] == 40.0
