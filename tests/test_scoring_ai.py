from slop_audit.models import ToolResult, ToolStatus, CATEGORY_AI
from slop_audit.scoring_ai import (
    FAMILY_WEIGHTS,
    compute_ai_likeness,
    to_ai_likeness_score,
)


def _ok(tool, score):
    return ToolResult(
        tool,
        ToolStatus.OK,
        "1",
        CATEGORY_AI,
        [],
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


def test_binoculars_family_not_double_counted():
    # two OK results in binoculars family with scores 20 and 80 → family value 50;
    # only that family → renormalize weight to 1.0, ensemble 50 (not double-weighted)
    results = [
        _ok("clarity", 20),
        _ok("binoculars", 80),
    ]
    out = compute_ai_likeness(results)
    assert abs(out["ensemble"] - 50.0) < 1e-9
    assert set(out["families_used"]) == {"binoculars"}
    assert abs(out["families_used"]["binoculars"] - 1.0) < 1e-9
    assert out["per_tool"]["clarity"] == 20
    assert out["per_tool"]["binoculars"] == 80
    # If clarity and binoculars were wrongly given separate 0.35 weights, still
    # mean-ish 50 — so also check with a second family that double-count would skew.
    with_deberta = results + [_ok("ai_detect", 100)]
    out2 = compute_ai_likeness(with_deberta)
    expected = 100 * (0.40 / 0.75) + 50 * (0.35 / 0.75)
    assert abs(out2["ensemble"] - expected) < 1e-9
    wrong_double = 100 * (0.40 / 1.10) + 20 * (0.35 / 1.10) + 80 * (0.35 / 1.10)
    assert abs(out2["ensemble"] - wrong_double) > 1e-6


def test_family_weights_match_design():
    assert FAMILY_WEIGHTS == {
        "deberta": 0.40,
        "binoculars": 0.35,
        "fastdetect": 0.25,
    }


def test_compute_ai_likeness_ignores_not_run():
    results = [
        _ok("ai_detect", 40),
        ToolResult(
            "fastdetectgpt",
            ToolStatus.NOT_RUN,
            None,
            CATEGORY_AI,
            [],
            "raw/fastdetectgpt",
            None,
            None,
            0,
            0,
            0,
            0,
            "missing",
            "",
        ),
    ]
    out = compute_ai_likeness(results)
    assert "fastdetect" not in out["families_used"]
    assert abs(out["ensemble"] - 40.0) < 1e-9
    assert abs(out["families_used"]["deberta"] - 1.0) < 1e-9


def test_agreement_by_spread():
    # identical family scores → HIGH
    same = [_ok("ai_detect", 50), _ok("fastdetectgpt", 50)]
    assert compute_ai_likeness(same)["agreement"] == "HIGH"
    # moderate spread across families
    mid = [_ok("ai_detect", 40), _ok("fastdetectgpt", 60)]
    assert compute_ai_likeness(mid)["agreement"] == "MEDIUM"
    # large spread
    wide = [_ok("ai_detect", 10), _ok("fastdetectgpt", 90)]
    assert compute_ai_likeness(wide)["agreement"] == "LOW"


def test_empty_results_ensemble_none():
    out = compute_ai_likeness([])
    assert out["ensemble"] is None
    assert out["agreement"] is None
    assert out["per_tool"] == {}
    assert out["families_used"] == {}


def test_to_ai_likeness_score_passthrough_hooks_exist():
    # hooks are documented per tool; unknown native → None (never invent)
    assert to_ai_likeness_score("ai_detect", None) is None
    assert to_ai_likeness_score("unknown_tool", {"score": 50}) is None
