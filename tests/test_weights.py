from slop_audit.weights import renormalize

def test_renormalize_drops_missing_and_rescales():
    w = {"a": 0.25, "b": 0.25, "c": 0.50}
    out = renormalize(w, {"a", "c"})
    assert set(out) == {"a", "c"}
    assert abs(sum(out.values()) - 1.0) < 1e-9
    assert abs(out["a"] - 0.25/0.75) < 1e-9
    assert abs(out["c"] - 0.50/0.75) < 1e-9

def test_renormalize_empty():
    assert renormalize({"a": 1.0}, set()) == {}
