from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def ensure_raw_dir(tool: str) -> Path:
    """Create and return raw/<tool>/ under project ROOT."""
    d = ROOT / "raw" / tool
    d.mkdir(parents=True, exist_ok=True)
    return d


def run_cmd(
    commands: list[str],
    timeout: float | None = None,
    cwd: str | Path | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Run a subprocess; never raises. Returns CompletedProcess-like dict."""
    try:
        proc = subprocess.run(
            commands,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
            env=env,
        )
        return {
            "returncode": proc.returncode,
            "stdout": proc.stdout or "",
            "stderr": proc.stderr or "",
        }
    except subprocess.TimeoutExpired as e:
        stdout = e.stdout or ""
        stderr = e.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        return {
            "returncode": -1,
            "stdout": stdout,
            "stderr": (stderr + f"\nTimeoutExpired: {timeout}").strip(),
        }
    except OSError as e:
        return {
            "returncode": 127,
            "stdout": "",
            "stderr": f"{type(e).__name__}: {e}",
        }
    except Exception as e:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": f"{type(e).__name__}: {e}",
        }


def write_raw(tool: str, name: str, content: str | bytes) -> Path:
    """Write content to raw/<tool>/<name>; creates the tool dir if needed."""
    d = ensure_raw_dir(tool)
    path = d / name
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")
    return path
