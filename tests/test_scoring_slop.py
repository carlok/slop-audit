from text_audit.models import ToolResult, ToolStatus, CATEGORY_SLOP
from text_audit.scoring_slop import compute_slop_index, band_for, SLOP_WEIGHTS


def _ok(tool, score):
    return ToolResult(tool, ToolStatus.OK, "1", CATEGORY_SLOP, [], f"raw/{tool}", {"score": score}, score, 0,0,0,0, "", "")


def test_slop_index_ignores_not_run():
    results = [_ok("slopscore", 40), ToolResult("dslop", ToolStatus.NOT_RUN, None, CATEGORY_SLOP, [], "raw/dslop", None, None, 0,0,0,0, "missing", "")]
    out = compute_slop_index(results)
    assert "dslop" not in out["weights_used"]
    assert out["score"] is not None


def test_band_for():
    assert band_for(10) == "LOW"
    assert band_for(40) == "MODERATE"
    assert band_for(60) == "HIGH"
    assert band_for(80) == "VERY HIGH"


def test_slop_weights_match_design():
    assert SLOP_WEIGHTS == {
        "slopscore": 0.25,
        "dslop": 0.20,
        "slopsift": 0.20,
        "ai_slop_detect": 0.10,
        "slop_lint": 0.05,
        "vale": 0.10,
        "prose": 0.10,
    }


def test_prose_tools_mean_into_prose_component():
    results = [
        _ok("slopscore", 40),
        _ok("proselint", 20),
        _ok("write_good", 40),
    ]
    out = compute_slop_index(results)
    assert "prose" in out["weights_used"]
    assert "proselint" not in out["weights_used"]
    assert abs(out["components"]["prose"] - 30.0) < 1e-9
    # only slopscore (0.25) + prose (0.10) → weights 0.25/0.35 and 0.10/0.35
    expected = 40 * (0.25 / 0.35) + 30 * (0.10 / 0.35)
    assert abs(out["score"] - expected) < 1e-9
    assert out["band"] == band_for(out["score"])


def test_empty_results_score_none():
    out = compute_slop_index([])
    assert out["score"] is None
    assert out["weights_used"] == {}
    assert out["components"] == {}
