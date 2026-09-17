from slop_audit.models import ToolResult, ToolStatus, CATEGORY_SLOP

def test_not_run_result_has_no_normalized_score():
    r = ToolResult(
        tool="dslop",
        status=ToolStatus.NOT_RUN,
        version=None,
        category=CATEGORY_SLOP,
        commands=["pip install dslop"],
        raw_dir="raw/dslop",
        native=None,
        normalized_score=None,
        findings_count=0,
        errors=0,
        warnings=0,
        info=0,
        reason="PackageNotFoundError: dslop",
        notes="",
    )
    assert r.status == ToolStatus.NOT_RUN
    assert r.normalized_score is None
    assert "dslop" in r.reason
