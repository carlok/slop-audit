"""Statistical baselines: textstat + sentence length / TTR / n-grams (no Slop Index)."""
from __future__ import annotations

import json
import re
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

from text_audit.adapters.base import ROOT, run_cmd, write_raw
from text_audit.models import CATEGORY_STATS, ToolResult, ToolStatus

TOOL = "stats"
VERSION = "textstat+local"
_PY = ROOT / "envs" / "slop" / "bin" / "python"

SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
WORD_RE = re.compile(r"\b\w+\b", re.UNICODE)


def _sentence_lengths(text: str) -> list[int]:
    parts = (
        [s.strip() for s in SENTENCE_SPLIT.split(text.strip()) if s.strip()]
        if text.strip()
        else []
    )
    return [len(WORD_RE.findall(s)) for s in parts]


def _ttr(words: list[str]) -> float:
    if not words:
        return 0.0
    return len(set(words)) / len(words)


def _top_ngrams(words: list[str], n: int, top_k: int = 10) -> list[dict[str, Any]]:
    if len(words) < n:
        return []
    grams = [" ".join(words[i : i + n]) for i in range(len(words) - n + 1)]
    counts = Counter(grams)
    return [{"ngram": g, "count": c} for g, c in counts.most_common(top_k)]


def _sentence_length_stats(lengths: list[int]) -> dict[str, float | int | None]:
    if not lengths:
        return {
            "mean": None,
            "median": None,
            "stdev": None,
            "cv": None,
            "min": None,
            "max": None,
        }
    mean = statistics.mean(lengths)
    median = statistics.median(lengths)
    stdev = statistics.pstdev(lengths)
    cv = (stdev / mean) if mean else None
    return {
        "mean": float(mean),
        "median": float(median),
        "stdev": float(stdev),
        "cv": float(cv) if cv is not None else None,
        "min": int(min(lengths)),
        "max": int(max(lengths)),
    }


def compute_stats(text: str, textstat_metrics: dict[str, Any] | None = None) -> dict[str, Any]:
    """Pure local metrics; textstat block optional (filled by run())."""
    words = [w.lower() for w in WORD_RE.findall(text)]
    lengths = _sentence_lengths(text)
    return {
        "sentence_length": _sentence_length_stats(lengths),
        "ttr": _ttr(words),
        "word_count": len(words),
        "unique_words": len(set(words)),
        "sentence_count": len(lengths),
        "top_bigrams": _top_ngrams(words, 2),
        "top_trigrams": _top_ngrams(words, 3),
        "textstat": textstat_metrics or {},
    }


def _textstat_via_python(text: str) -> tuple[dict[str, Any] | None, str]:
    """Return (metrics, error_reason)."""
    if not _PY.is_file():
        return None, f"missing python: {_PY}"
    staging = ROOT / "raw" / TOOL
    staging.mkdir(parents=True, exist_ok=True)
    text_path = staging / "_input_for_textstat.txt"
    text_path.write_text(text, encoding="utf-8")
    script = (
        "import json, textstat, pathlib\n"
        f"text = pathlib.Path({str(text_path)!r}).read_text(encoding='utf-8')\n"
        "out = {\n"
        "  'flesch_reading_ease': textstat.flesch_reading_ease(text),\n"
        "  'flesch_kincaid_grade': textstat.flesch_kincaid_grade(text),\n"
        "  'gunning_fog': textstat.gunning_fog(text),\n"
        "  'smog_index': textstat.smog_index(text),\n"
        "  'coleman_liau_index': textstat.coleman_liau_index(text),\n"
        "  'automated_readability_index': textstat.automated_readability_index(text),\n"
        "  'dale_chall_readability_score': textstat.dale_chall_readability_score(text),\n"
        "  'avg_sentence_length': textstat.avg_sentence_length(text),\n"
        "  'avg_syllables_per_word': textstat.avg_syllables_per_word(text),\n"
        "  'lexicon_count': textstat.lexicon_count(text, removepunct=True),\n"
        "  'sentence_count': textstat.sentence_count(text),\n"
        "  'char_count': textstat.char_count(text, ignore_spaces=True),\n"
        "}\n"
        "print(json.dumps(out))\n"
    )
    proc = run_cmd([str(_PY), "-c", script], timeout=60)
    if proc["returncode"] != 0 or not (proc["stdout"] or "").strip():
        return None, f"textstat failed: {(proc['stderr'] or proc['stdout'] or '')[:300]}"
    try:
        return json.loads(proc["stdout"]), ""
    except json.JSONDecodeError as e:
        return None, f"textstat JSON error: {e}"


def _not_run(reason: str, commands: list[str]) -> ToolResult:
    return ToolResult(
        tool=TOOL,
        status=ToolStatus.NOT_RUN,
        version=VERSION,
        category=CATEGORY_STATS,
        commands=commands,
        raw_dir=f"raw/{TOOL}",
        native=None,
        normalized_score=None,
        findings_count=0,
        errors=0,
        warnings=0,
        info=0,
        reason=reason,
    )


def run(input_path: Path, word_count: int) -> ToolResult:
    path = Path(input_path)
    commands = [str(_PY), "-c", "<textstat+local stats>"]
    if not _PY.is_file():
        return _not_run(f"missing python: {_PY}", commands)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        return ToolResult(
            tool=TOOL,
            status=ToolStatus.ERROR,
            version=VERSION,
            category=CATEGORY_STATS,
            commands=commands,
            raw_dir=f"raw/{TOOL}",
            native=None,
            normalized_score=None,
            findings_count=0,
            errors=0,
            warnings=0,
            info=0,
            reason=f"read error: {e}",
        )

    ts, err = _textstat_via_python(text)
    if ts is None:
        return _not_run(err or "textstat unavailable", commands)

    native = compute_stats(text, textstat_metrics=ts)
    wc = max(int(native.get("word_count") or word_count or 1), 1)
    native["densities_per_1k"] = {
        "sentences": (native.get("sentence_count") or 0) / wc * 1000.0,
        "unique_words": (native.get("unique_words") or 0) / wc * 1000.0,
    }

    write_raw(TOOL, "result.json", json.dumps(native, indent=2, default=str) + "\n")
    write_raw(TOOL, "returncode.txt", "0")
    return ToolResult(
        tool=TOOL,
        status=ToolStatus.OK,
        version=VERSION,
        category=CATEGORY_STATS,
        commands=commands,
        raw_dir=f"raw/{TOOL}",
        native=native,
        normalized_score=None,
        findings_count=0,
        errors=0,
        warnings=0,
        info=0,
        reason="",
        notes="descriptive stats only; not used in Slop Index",
    )


run.tool = TOOL  # type: ignore[attr-defined]
run.version = VERSION  # type: ignore[attr-defined]
