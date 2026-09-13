"""Unit + integration tests for Vale/prose adapters F–J + stats."""
from __future__ import annotations

from pathlib import Path

import pytest

from text_audit.adapters.base import ROOT
from text_audit.models import CATEGORY_PROSE, CATEGORY_STATS, ToolStatus

FIX = ROOT / "tests" / "fixtures" / "short.txt"

VALE_STDOUT = """\
{
  "/tmp/x.txt": [
    {
      "Check": "Slop.Delve",
      "Severity": "warning",
      "Message": "Avoid formulaic 'delve'.",
      "Match": "delve",
      "Line": 1
    },
    {
      "Check": "write-good.TooWordy",
      "Severity": "error",
      "Message": "'It is' is too wordy.",
      "Match": "It is",
      "Line": 1
    },
    {
      "Check": "Slop.MoreoverFurthermore",
      "Severity": "suggestion",
      "Message": "Heavy transition 'Moreover'.",
      "Match": "Moreover",
      "Line": 2
    }
  ]
}
"""

PROSELINT_STDOUT = """\
{
  "result": {
    "file:///tmp/x.txt": {
      "diagnostics": [
        {
          "check_path": "lexical_illusions",
          "message": "There's a lexical illusion.",
          "pos": [1, 10],
          "span": [10, 20]
        },
        {
          "check_path": "typography.symbols",
          "message": "Use a proper dash.",
          "pos": [2, 1],
          "span": [30, 31]
        }
      ]
    }
  }
}
"""

WRITE_GOOD_STDOUT = """\
x.txt:1:0:"It is" is wordy or unneeded
x.txt:1:20:"carefully" can weaken meaning
x.txt:2:5:"there is" is wordy or unneeded
"""

LT_STDOUT = """\
{
  "software": {"name": "LanguageTool", "version": "6.6"},
  "matches": [
    {
      "message": "Word repetition",
      "offset": 10,
      "length": 5,
      "rule": {"id": "ENGLISH_WORD_REPEAT_RULE", "issueType": "duplication",
               "category": {"id": "MISC", "name": "Miscellaneous"}}
    },
    {
      "message": "Possible typo",
      "offset": 20,
      "length": 3,
      "rule": {"id": "MORFOLOGIK_RULE_EN_US", "issueType": "misspelling",
               "category": {"id": "TYPOS", "name": "Possible Typo"}}
    }
  ]
}
"""


def test_parse_vale_maps_severities():
    from text_audit.adapters.vale_adapter import parse_stdout
    from text_audit.normalize import normalize_from_counts

    parsed = parse_stdout(VALE_STDOUT, word_count=100)
    assert parsed["errors"] == 1
    assert parsed["warnings"] == 1
    assert parsed["info"] == 1
    assert parsed["findings_count"] == 3
    assert parsed["normalized_score"] == pytest.approx(
        normalize_from_counts(1, 1, 1, 100)
    )


def test_parse_proselint_counts_diagnostics():
    from text_audit.adapters.proselint_adapter import parse_stdout
    from text_audit.normalize import normalize_from_counts

    parsed = parse_stdout(PROSELINT_STDOUT, word_count=50)
    assert parsed["warnings"] == 2
    assert parsed["errors"] == 0
    assert parsed["findings_count"] == 2
    assert parsed["normalized_score"] == pytest.approx(
        normalize_from_counts(0, 2, 0, 50)
    )


def test_parse_write_good_counts_lines():
    from text_audit.adapters.write_good import parse_stdout
    from text_audit.normalize import normalize_from_counts

    parsed = parse_stdout(WRITE_GOOD_STDOUT, word_count=40)
    assert parsed["warnings"] == 3
    assert parsed["findings_count"] == 3
    assert parsed["normalized_score"] == pytest.approx(
        normalize_from_counts(0, 3, 0, 40)
    )


def test_parse_languagetool_counts_matches():
    from text_audit.adapters.languagetool_adapter import parse_stdout
    from text_audit.normalize import normalize_from_counts

    parsed = parse_stdout(LT_STDOUT, word_count=80)
    assert parsed["findings_count"] == 2
    assert parsed["warnings"] + parsed["info"] + parsed["errors"] == 2
    assert parsed["normalized_score"] == pytest.approx(
        normalize_from_counts(
            parsed["errors"], parsed["warnings"], parsed["info"], 80
        )
    )


def test_parse_harper_reuses_vale_json():
    from text_audit.adapters.harper_adapter import parse_stdout
    from text_audit.normalize import normalize_from_counts

    harper_json = """\
{
  "/tmp/x.txt": [
    {"Check": "Harper.ThenThan", "Severity": "warning", "Message": "Use than.", "Match": "then", "Line": 1},
    {"Check": "Harper.BetterOffWith", "Severity": "error", "Message": "off.", "Match": "of", "Line": 2}
  ]
}
"""
    parsed = parse_stdout(harper_json, word_count=60)
    assert parsed["errors"] == 1
    assert parsed["warnings"] == 1
    assert parsed["normalized_score"] == pytest.approx(
        normalize_from_counts(1, 1, 0, 60)
    )


def test_stats_compute_has_required_keys():
    from text_audit.adapters.stats_adapter import compute_stats

    text = (
        "Hello world. This is a test sentence with several words. "
        "Another sentence follows here for variety and length."
    )
    native = compute_stats(text)
    for key in (
        "sentence_length",
        "ttr",
        "top_bigrams",
        "top_trigrams",
        "textstat",
    ):
        assert key in native
    sl = native["sentence_length"]
    for k in ("mean", "median", "stdev", "cv", "min", "max"):
        assert k in sl
    assert isinstance(native["ttr"], float)
    assert isinstance(native["top_bigrams"], list)
    assert isinstance(native["top_trigrams"], list)


def _exists(rel: str) -> bool:
    return (ROOT / rel).exists()


@pytest.mark.parametrize(
    "mod_name, tool, category, probe",
    [
        (
            "text_audit.adapters.vale_adapter",
            "vale",
            CATEGORY_PROSE,
            "tools/vale/vale",
        ),
        (
            "text_audit.adapters.proselint_adapter",
            "proselint",
            CATEGORY_PROSE,
            "envs/slop/bin/proselint",
        ),
        (
            "text_audit.adapters.write_good",
            "write_good",
            CATEGORY_PROSE,
            "tools/node_modules/.bin/write-good",
        ),
        (
            "text_audit.adapters.harper_adapter",
            "harper",
            CATEGORY_PROSE,
            "tools/vale/vale",
        ),
        (
            "text_audit.adapters.languagetool_adapter",
            "languagetool",
            CATEGORY_PROSE,
            "tools/languagetool/LanguageTool-6.6/languagetool-commandline.jar",
        ),
        (
            "text_audit.adapters.stats_adapter",
            "stats",
            CATEGORY_STATS,
            "envs/slop/bin/python",
        ),
    ],
)
def test_integration_run_or_not_run(mod_name, tool, category, probe):
    import importlib

    mod = importlib.import_module(mod_name)
    result = mod.run(FIX, word_count=9)
    assert result.tool == tool
    assert result.category == category
    if _exists(probe):
        assert result.status in (ToolStatus.OK, ToolStatus.ERROR, ToolStatus.NOT_RUN)
        if result.status == ToolStatus.OK:
            if category == CATEGORY_STATS:
                assert result.normalized_score is None
                assert isinstance(result.native, dict)
                assert "sentence_length" in result.native
            else:
                assert result.normalized_score is not None
                assert 0.0 <= float(result.normalized_score) <= 100.0
            raw = ROOT / "raw" / tool
            assert raw.is_dir()
        elif result.status == ToolStatus.NOT_RUN:
            assert result.normalized_score is None
            assert result.reason
    else:
        assert result.status == ToolStatus.NOT_RUN
        assert result.normalized_score is None
        assert result.reason


def test_adapters_registered_include_fj_stats():
    from text_audit.adapters import ALL_ADAPTERS, get_adapters

    names = {getattr(a, "tool", a.__name__) for a in get_adapters()}
    expected = {
        "vale",
        "proselint",
        "write_good",
        "harper",
        "languagetool",
        "stats",
    }
    assert expected <= names
    assert len(ALL_ADAPTERS) >= 11


def test_vale_ini_and_slop_rules_exist():
    ini = ROOT / "vale" / ".vale.ini"
    assert ini.is_file()
    text = ini.read_text(encoding="utf-8")
    assert "StylesPath" in text
    assert "write-good" in text or "Slop" in text
    slop = ROOT / "vale" / "styles" / "Slop"
    assert slop.is_dir()
    names = {p.stem for p in slop.glob("*.yml")}
    for required in (
        "ItIsImportantToNote",
        "Delve",
        "TestamentTo",
        "InTodaysWorld",
        "NotMerelyBut",
        "MoreoverFurthermore",
    ):
        assert required in names
