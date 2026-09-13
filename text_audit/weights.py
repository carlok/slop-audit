from __future__ import annotations

def renormalize(weights: dict[str, float], available: set[str]) -> dict[str, float]:
    kept = {k: v for k, v in weights.items() if k in available}
    total = sum(kept.values())
    if total <= 0:
        return {}
    return {k: v / total for k, v in kept.items()}
