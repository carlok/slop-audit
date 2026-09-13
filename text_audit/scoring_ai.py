from __future__ import annotations

from typing import Any

from text_audit.models import ToolResult, ToolStatus
from text_audit.weights import renormalize

FAMILY_WEIGHTS: dict[str, float] = {
    "deberta": 0.40,
    "binoculars": 0.35,
    "fastdetect": 0.25,
}

# Tool → method family (Clarity + Binoculars share binoculars; do not double-weight).
TOOL_FAMILY: dict[str, str] = {
    "ai_detect": "deberta",
    "clarity": "binoculars",
    "binoculars": "binoculars",
    "fastdetectgpt": "fastdetect",
}

# Agreement by max−min spread of per-tool AI-likeness scores (0–100).
_SPREAD_HIGH = 20.0
_SPREAD_MEDIUM = 40.0


def agreement_for_spread(spread: float) -> str:
    if spread < _SPREAD_HIGH:
        return "HIGH"
    if spread < _SPREAD_MEDIUM:
        return "MEDIUM"
    return "LOW"


def _native_numeric(native: Any) -> float | None:
    if isinstance(native, (int, float)):
        return float(native)
    if isinstance(native, dict):
        for key in ("ai_likeness", "score", "ai_score"):
            val = native.get(key)
            if isinstance(val, (int, float)):
                return float(val)
        for key in ("ai_probability", "probability"):
            val = native.get(key)
            if isinstance(val, (int, float)):
                f = float(val)
                if 0.0 <= f <= 1.0:
                    return f * 100.0
                return f
    return None


def to_ai_likeness_score(tool: str, native: Any) -> float | None:
    """Directional 0–100 AI-likeness (higher = more AI-like) from native output.

    Prefer ``ToolResult.normalized_score`` when adapters already normalized.
    Per-tool hooks exist so each detector's polarity can be documented; unknown
    tools or unhandled natives return None (never invent a score).
    """
    if tool not in TOOL_FAMILY:
        return None
    # Placeholder hooks: polarity must match each tool's documented semantics.
    # Until adapters land, extract an explicit score field when present.
    if tool in ("ai_detect", "clarity", "binoculars", "fastdetectgpt"):
        return _native_numeric(native)
    return None


def _score_for_result(r: ToolResult) -> float | None:
    if r.status != ToolStatus.OK:
        return None
    if r.tool not in TOOL_FAMILY:
        return None
    if r.normalized_score is not None:
        return float(r.normalized_score)
    return to_ai_likeness_score(r.tool, r.native)


def compute_ai_likeness(results: list[ToolResult]) -> dict:
    """Family-aware AI-Likeness ensemble; separate from Slop Index."""
    per_tool: dict[str, float] = {}
    family_scores: dict[str, list[float]] = {}

    for r in results:
        score = _score_for_result(r)
        if score is None:
            continue
        per_tool[r.tool] = score
        family = TOOL_FAMILY[r.tool]
        family_scores.setdefault(family, []).append(score)

    if not family_scores:
        return {
            "ensemble": None,
            "agreement": None,
            "per_tool": {},
            "families_used": {},
        }

    family_values = {
        fam: sum(scores) / len(scores) for fam, scores in family_scores.items()
    }
    families_used = renormalize(FAMILY_WEIGHTS, set(family_values))
    ensemble = sum(family_values[f] * w for f, w in families_used.items())

    tool_vals = list(per_tool.values())
    if len(tool_vals) >= 2:
        spread = max(tool_vals) - min(tool_vals)
    else:
        spread = 0.0
    agreement = agreement_for_spread(spread)

    return {
        "ensemble": ensemble,
        "agreement": agreement,
        "per_tool": per_tool,
        "families_used": families_used,
    }
