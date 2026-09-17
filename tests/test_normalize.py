import math
from slop_audit.normalize import (
    weighted_findings,
    density,
    normalized_score,
    normalize_from_counts,
    MIN_WORD_COUNT_FOR_DENSITY,
)

def test_weighted_findings():
    assert weighted_findings(1, 2, 3) == 3*1 + 2*2 + 1*3

def test_normalized_score_zero_density():
    assert normalized_score(0.0) == 0.0

def test_normalize_from_counts_matches_formula():
    w = weighted_findings(0, 5, 0)
    d = density(w, 1000)
    expected = 100 * (1 - math.exp(-d / 10))
    assert abs(normalize_from_counts(0, 5, 0, 1000) - expected) < 1e-9

def test_density_uses_min_word_count_floor():
    w = weighted_findings(0, 1, 0)
    assert density(w, 22) == density(w, MIN_WORD_COUNT_FOR_DENSITY)
    assert density(w, 22) < (w / 22 * 1000.0)
