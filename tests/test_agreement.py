from text_audit.agreement import independent_agreement


def test_independent_agreement_counts_unique_tools():
    phenomena = {
        "em_dash": ["slop_lint", "vale", "slop_lint"],
        "hedging": ["proselint"],
        "buzzwords": ["dslop", "slopsift", "vale"],
    }
    out = independent_agreement(phenomena)
    by_name = {row["phenomenon"]: row for row in out}
    assert by_name["em_dash"]["count"] == 2
    assert set(by_name["em_dash"]["tools"]) == {"slop_lint", "vale"}
    assert by_name["hedging"]["count"] == 1
    assert by_name["buzzwords"]["count"] == 3
    # highest agreement first
    assert out[0]["phenomenon"] == "buzzwords"
