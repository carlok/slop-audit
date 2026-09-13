from __future__ import annotations
import math

def weighted_findings(errors: int, warnings: int, info: int) -> float:
    return 3 * errors + 2 * warnings + 1 * info

def density(weighted: float, word_count: int) -> float:
    if word_count <= 0:
        return 0.0
    return weighted / word_count * 1000.0

def normalized_score(dens: float) -> float:
    return 100.0 * (1.0 - math.exp(-dens / 10.0))

def normalize_from_counts(errors: int, warnings: int, info: int, word_count: int) -> float:
    return normalized_score(density(weighted_findings(errors, warnings, info), word_count))
