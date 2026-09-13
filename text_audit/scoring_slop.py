from __future__ import annotations

from text_audit.models import ToolResult, ToolStatus
from text_audit.weights import renormalize

SLOP_WEIGHTS: dict[str, float] = {
    "slopscore": 0.25,
    "dslop": 0.20,
    "slopsift": 0.20,
    "ai_slop_detect": 0.10,
    "slop_lint": 0.05,
    "vale": 0.10,
    "prose": 0.10,
}

PROSE_TOOLS = frozenset({"proselint", "write_good", "harper", "languagetool"})


def band_for(score: float) -> str:
    if score < 25:
        return "LOW"
    if score < 50:
        return "MODERATE"
    if score < 75:
        return "HIGH"
    return "VERY HIGH"


def compute_slop_index(results: list[ToolResult]) -> dict:
    components: dict[str, float] = {}
    prose_scores: list[float] = []

    for r in results:
        if r.status != ToolStatus.OK or r.normalized_score is None:
            continue
        if r.tool in PROSE_TOOLS:
            prose_scores.append(float(r.normalized_score))
        elif r.tool in SLOP_WEIGHTS:
            components[r.tool] = float(r.normalized_score)

    if prose_scores:
        components["prose"] = sum(prose_scores) / len(prose_scores)

    weights_used = renormalize(SLOP_WEIGHTS, set(components))
    if not weights_used:
        return {
            "score": None,
            "band": None,
            "weights_used": {},
            "components": {},
        }

    score = sum(components[k] * w for k, w in weights_used.items())
    return {
        "score": score,
        "band": band_for(score),
        "weights_used": weights_used,
        "components": components,
    }
