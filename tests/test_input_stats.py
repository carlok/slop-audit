from pathlib import Path
from slop_audit.input_stats import compute_input_stats

FIX = Path(__file__).parent / "fixtures" / "short.txt"

def test_compute_input_stats_basic():
    s = compute_input_stats(FIX)
    assert s.words >= 8
    assert s.sentences >= 2
    assert s.paragraphs == 2
    assert len(s.sha256) == 64
    assert s.bytes > 0
