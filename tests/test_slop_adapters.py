"""Unit + integration tests for deterministic slop adapters A–E."""
from __future__ import annotations

from pathlib import Path

import pytest

from slop_audit.adapters.base import ROOT
from slop_audit.models import CATEGORY_SLOP, ToolStatus

FIX = ROOT / "tests" / "fixtures" / "short.txt"

SLOPSCORE_STDOUT = """\
{
  "version": "0.13.0",
  "input": {"source_type": "text", "source": "x.txt", "profile": "blog", "language": "en", "word_count": 58},
  "score": {
    "slop_score": 72.5,
    "label": "high",
    "confidence": 0.8,
    "strictness": "conservative",
    "abstained": false,
    "abstention_reason": null
  },
  "dimensions": {"lexical_markers": 0.5},
  "evidence": [
    {"rule_id": "A", "severity": "high", "span": "x", "explanation": "e"},
    {"rule_id": "B", "severity": "medium", "span": "y", "explanation": "e"},
    {"rule_id": "C", "severity": "low", "span": "z", "explanation": "e"},
    {"rule_id": "D", "severity": "low", "span": "w", "explanation": "e"}
  ],
  "warnings": ["note"]
}
"""

DSLOP_STDOUT = """\
dslop: 2 violations in 1 file
  tests/fixtures/short.txt:1:14 summary-capstone
  tests/fixtures/short.txt:1:20 em-dash

fix:
  summary-capstone: cut the paragraph-ending capstone
  em-dash: rewrite without em-dash
"""

SLOPSIFT_STDOUT = """\
[
  {
    "filePath": "x.txt",
    "rulesetVersion": "slopsift@0.11.0",
    "messages": [
      {"ruleId": "ai-style/a", "level": "error", "severity": 2, "message": "e"},
      {"ruleId": "ai-style/b", "level": "warn", "severity": 1, "message": "w"},
      {"ruleId": "ai-style/c", "level": "info", "severity": 0, "message": "i"}
    ],
    "errorCount": 1,
    "warningCount": 1,
    "infoCount": 1,
    "wordCount": 58,
    "findingsPerThousandWords": 50
  }
]
"""

AI_SLOP_STDOUT = """\
{
  "path": "x.txt",
  "ai_score": 83,
  "verdict": "LIKELY_AI",
  "stats": {"chars": 100, "words": 20, "lines": 2, "hits": 3, "density_per_100w": 15.0, "by_kind": {"phrase": 3}},
  "hits": [
    {"line": 1, "col": 1, "kind": "phrase", "match": "delve"},
    {"line": 1, "col": 10, "kind": "phrase", "match": "tapestry"},
    {"line": 2, "col": 1, "kind": "char:em_dash", "match": "—"}
  ]
}
"""

SLOP_LINT_STDOUT = """\

x.txt
  1: ✗ em-dash ×1  some text with —
  1: ⚠ word "delve"
  1: ⚠ word "tapestry"
  1: ⚠ "in today's ... world" intro

1 em-dash failure(s), 3 warning(s) across 1 file(s).
FAIL on em-dash; warnings are prompts to review, not bans.
"""


def test_parse_slopscore_uses_native_score_and_severities():
    from slop_audit.adapters.slopscore import parse_stdout

    parsed = parse_stdout(SLOPSCORE_STDOUT, word_count=58)
    assert parsed["errors"] == 1
    assert parsed["warnings"] == 1
    assert parsed["info"] == 2
    assert parsed["findings_count"] == 4
    assert parsed["normalized_score"] == pytest.approx(72.5)
    assert parsed["native"]["score"]["slop_score"] == 72.5


def test_parse_dslop_counts_violations_and_normalizes():
    from slop_audit.adapters.dslop_adapter import parse_stdout
    from slop_audit.normalize import normalize_from_counts

    parsed = parse_stdout(DSLOP_STDOUT, word_count=100)
    assert parsed["errors"] == 0
    assert parsed["warnings"] == 2
    assert parsed["info"] == 0
    assert parsed["findings_count"] == 2
    assert parsed["normalized_score"] == pytest.approx(
        normalize_from_counts(0, 2, 0, 100)
    )


def test_parse_slopsift_uses_counts():
    from slop_audit.adapters.slopsift import parse_stdout
    from slop_audit.normalize import normalize_from_counts

    parsed = parse_stdout(SLOPSIFT_STDOUT, word_count=58)
    assert parsed["errors"] == 1
    assert parsed["warnings"] == 1
    assert parsed["info"] == 1
    assert parsed["findings_count"] == 3
    assert parsed["normalized_score"] == pytest.approx(
        normalize_from_counts(1, 1, 1, 58)
    )


def test_parse_ai_slop_detect_uses_ai_score():
    from slop_audit.adapters.ai_slop_detect import parse_stdout

    parsed = parse_stdout(AI_SLOP_STDOUT, word_count=20)
    assert parsed["normalized_score"] == pytest.approx(83.0)
    assert parsed["findings_count"] == 3
    assert parsed["warnings"] == 3
    assert parsed["native"]["verdict"] == "LIKELY_AI"


def test_parse_slop_lint_counts_emdash_and_warnings():
    from slop_audit.adapters.slop_lint import parse_stdout
    from slop_audit.normalize import normalize_from_counts

    parsed = parse_stdout(SLOP_LINT_STDOUT, word_count=50)
    assert parsed["errors"] == 1
    assert parsed["warnings"] == 3
    assert parsed["findings_count"] == 4
    assert parsed["normalized_score"] == pytest.approx(
        normalize_from_counts(1, 3, 0, 50)
    )


def _bin_exists(rel: str) -> bool:
    return (ROOT / rel).is_file()


@pytest.mark.parametrize(
    "mod_name, tool, bin_rel",
    [
        ("slop_audit.adapters.slopscore", "slopscore", "envs/slop/bin/slopscore-lint"),
        ("slop_audit.adapters.dslop_adapter", "dslop", "envs/slop/bin/dslop"),
        ("slop_audit.adapters.slopsift", "slopsift", "tools/node_modules/.bin/slopsift"),
        ("slop_audit.adapters.ai_slop_detect", "ai_slop_detect", "envs/slop/bin/ai-slop"),
        ("slop_audit.adapters.slop_lint", "slop_lint", "tools/node_modules/slop-lint/slop-lint.mjs"),
    ],
)
def test_integration_run_or_not_run(mod_name, tool, bin_rel):
    import importlib

    mod = importlib.import_module(mod_name)
    result = mod.run(FIX, word_count=9)
    assert result.tool == tool
    assert result.category == CATEGORY_SLOP
    if _bin_exists(bin_rel):
        assert result.status in (ToolStatus.OK, ToolStatus.ERROR)
        if result.status == ToolStatus.OK:
            assert result.normalized_score is not None
            assert 0.0 <= float(result.normalized_score) <= 100.0
            raw = ROOT / "raw" / tool
            assert raw.is_dir()
            assert any(raw.iterdir())
    else:
        assert result.status == ToolStatus.NOT_RUN
        assert result.normalized_score is None
        assert result.reason


def test_adapters_registered():
    from slop_audit.adapters import ALL_ADAPTERS, get_adapters

    names = {getattr(a, "tool", a.__name__) for a in get_adapters()}
    expected = {"slopscore", "dslop", "slopsift", "ai_slop_detect", "slop_lint"}
    assert expected <= names
    assert len(ALL_ADAPTERS) >= 5
