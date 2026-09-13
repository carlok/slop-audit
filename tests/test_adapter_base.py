from text_audit.adapters.base import run_cmd


def test_run_cmd_captures_failure_without_raising():
    result = run_cmd(["bash", "-c", "echo nope >&2; exit 7"])
    assert result["returncode"] == 7
    assert "nope" in result["stderr"]
