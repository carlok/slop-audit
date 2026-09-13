from __future__ import annotations
import math

# Soft floor for density denominators: short pastes otherwise saturate
# normalized_score from a single finding (e.g. 1 warning @ 22 words ≈ 100).
MIN_WORD_COUNT_FOR_DENSITY = 100


def weighted_findings(errors: int, warnings: int, info: int) -> float:
    return 3 * errors + 2 * warnings + 1 * info


def density(weighted: float, word_count: int) -> float:
    """weighted / max(word_count, MIN) * 1000; then score = 100*(1-exp(-d/10))."""
    if word_count <= 0:
        return 0.0
    denom = max(int(word_count), MIN_WORD_COUNT_FOR_DENSITY)
    return weighted / denom * 1000.0


def normalized_score(dens: float) -> float:
    return 100.0 * (1.0 - math.exp(-dens / 10.0))


def normalize_from_counts(errors: int, warnings: int, info: int, word_count: int) -> float:
    return normalized_score(density(weighted_findings(errors, warnings, info), word_count))
