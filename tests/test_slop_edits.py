from slop_audit.models import ToolResult, ToolStatus, CATEGORY_SLOP, CATEGORY_PROSE, CATEGORY_AI
from slop_audit.slop_edits import collect_slop_edit_suggestions


def _ok(tool, category, native):
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


def test_extracts_vale_and_dedupes_same_quote_across_tools():
    vale = _ok(
        "vale",
        CATEGORY_PROSE,
        {
            "alerts": [
                {
                    "Check": "write-good.TooWordy",
                    "Message": "'It seems that' is too wordy.",
                    "Match": "It seems that",
                    "Line": 9,
                }
            ]
        },
    )
    wg = _ok(
        "write_good",
        CATEGORY_PROSE,
        {
            "findings": [
                '/x.txt:9:0:"It seems that" is wordy or unneeded',
            ]
        },
    )
    items = collect_slop_edit_suggestions([vale, wg])
    quotes = [i.get("quote") for i in items]
    assert quotes.count("It seems that") == 1
    assert items[0]["tool"] == "vale"


def test_skips_ai_authorship_tools():
    ai = _ok(
        "ai_detect",
        CATEGORY_AI,
        {"sentences": [{"sentence": "Hi", "label": "AI", "ai_prob": 0.9}]},
    )
    assert collect_slop_edit_suggestions([ai]) == []


def test_dslop_uses_fix_message():
    native = {
        "stdout": (
            "dslop: 1 violation in 1 file\n"
            "  /tmp/t.txt:15:59 demonstrative-is\n"
            "\n"
            "FIX:\n"
            '  demonstrative-is: rewrite without "this is the"\n'
        ),
        "violations": ["/tmp/t.txt:15:59 demonstrative-is"],
    }
    items = collect_slop_edit_suggestions([_ok("dslop", CATEGORY_SLOP, native)])
    assert len(items) == 1
    assert items[0]["rule"] == "demonstrative-is"
    assert "rewrite without" in items[0]["message"]
    assert items[0]["location"] == "line 15:59"


def test_write_good_parses_quoted_span():
    wg = _ok(
        "write_good",
        CATEGORY_PROSE,
        {"findings": ['/x.txt:7:62:"only" can weaken meaning']},
    )
    items = collect_slop_edit_suggestions([wg])
    assert items[0]["quote"] == "only"
    assert items[0]["message"] == "can weaken meaning"
