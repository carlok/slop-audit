from slop_audit.env_inspect import inspect_environment

def test_inspect_environment_has_required_keys():
    env = inspect_environment()
    for key in ["os", "arch", "cpu", "ram_bytes", "python", "disk_free_bytes"]:
        assert key in env
    assert env["python"]
