from slop_audit.models import CATEGORY_AI, CATEGORY_PROSE, CATEGORY_SLOP, ToolResult, ToolStatus
from slop_audit.phenomena import build_phenomena_map, corroborated_findings


def _ok(tool: str, category: str, native) -> ToolResult:
    return ToolResult(
        tool=tool,
        status=ToolStatus.OK,
        version="1",
        category=category,
        commands=[],
        raw_dir=f"raw/{tool}",
        native=native,
        normalized_score=10.0,
        findings_count=1,
        errors=0,
        warnings=1,
        info=0,
        reason="",
    )


def test_corroborated_when_two_tools_share_quoted_span():
    native_vale = {
        "alerts": [
            {
                "Check": "Slop/Delve",
                "Message": "Avoid 'delve'",
                "Match": "delve",
                "Line": 1,
            }
        ]
    }
    native_wg = {"findings": ['input.txt:1:5:"delve" can weaken meaning']}
    results = [
        _ok("vale", CATEGORY_PROSE, native_vale),
        _ok("write_good", CATEGORY_PROSE, native_wg),
    ]
    corr = corroborated_findings(results)
    assert len(corr) == 1
    assert corr[0]["count"] == 2
    assert set(corr[0]["tools"]) == {"vale", "write_good"}
    assert corr[0]["phenomenon"] == "delve"


def test_single_tool_label_not_corroborated():
    results = [
        _ok(
            "dslop",
            CATEGORY_SLOP,
            {
                "stdout": "input.txt:1:1 hedging-word\n",
                "violations": ["input.txt:1:1 hedging-word"],
            },
        ),
    ]
    assert corroborated_findings(results) == []
    phenomena = build_phenomena_map(results)
    assert len(phenomena) == 1


def test_ai_authorship_tools_excluded_from_phenomena():
    results = [
        _ok(
            "ai_detect",
            CATEGORY_AI,
            {"model_ai_pct": 55.0, "sentences": []},
        ),
        _ok(
            "vale",
            CATEGORY_PROSE,
            {
                "alerts": [
                    {
                        "Check": "Slop/Delve",
                        "Message": "Avoid delve",
                        "Match": "delve",
                    }
                ]
            },
        ),
    ]
    phenomena = build_phenomena_map(results)
    assert all("ai_detect" not in tools for tools in phenomena.values())
