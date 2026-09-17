from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from typing import Any


def _run_version(cmd: list[str]) -> str | None:
    """Run a version command; return first-line stdout/stderr or None if missing/failing."""
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return None
    out = (proc.stdout or "").strip() or (proc.stderr or "").strip()
    if not out:
        return None
    return out.splitlines()[0].strip()


def _tool_version(binary: str, *args: str) -> str | None:
    if shutil.which(binary) is None:
        return None
    return _run_version([binary, *args])


def _ram_bytes() -> int | None:
    try:
        with open("/proc/meminfo", encoding="utf-8") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    parts = line.split()
                    # MemTotal is in kB
                    return int(parts[1]) * 1024
    except (OSError, ValueError, IndexError):
        pass
    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        if isinstance(pages, int) and isinstance(page_size, int) and pages > 0:
            return pages * page_size
    except (ValueError, OSError, AttributeError):
        pass
    return None


def _cpu_model() -> str:
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as f:
            for line in f:
                if line.lower().startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or platform.machine() or ""


def _detect_gpu() -> str:
    # NVIDIA
    if shutil.which("nvidia-smi"):
        try:
            proc = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=name",
                    "--format=csv,noheader",
                ],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            names = [ln.strip() for ln in (proc.stdout or "").splitlines() if ln.strip()]
            if names:
                return ", ".join(names)
        except (OSError, subprocess.TimeoutExpired):
            pass
        ver = _run_version(["nvidia-smi", "--version"])
        if ver:
            return ver

    # AMD ROCm
    if shutil.which("rocm-smi"):
        out = _run_version(["rocm-smi", "--showproductname"])
        if out:
            return out
        return "ROCm (rocm-smi present)"

    # Linux DRM / sysfs best-effort
    try:
        cards = sorted(
            p for p in os.listdir("/sys/class/drm") if p.startswith("card") and "-" not in p
        )
        names: list[str] = []
        for card in cards:
            for rel in ("device/product_name", "device/label", "device/vendor"):
                path = f"/sys/class/drm/{card}/{rel}"
                try:
                    with open(path, encoding="utf-8") as f:
                        val = f.read().strip()
                    if val:
                        names.append(val)
                        break
                except OSError:
                    continue
        if names:
            return ", ".join(names)
    except OSError:
        pass

    return "none detected"


def _disk_free_bytes() -> int | None:
    try:
        return int(shutil.disk_usage(".").free)
    except OSError:
        return None


def inspect_environment() -> dict[str, Any]:
    """Collect local environment facts for audit logs.

    All required keys are always present; missing tools may be None or "".
    """
    python_ver = sys.version.split()[0]
    python_str = f"{platform.python_implementation()} {python_ver}"

    return {
        "os": f"{platform.system()} {platform.release()}".strip(),
        "arch": platform.machine() or "",
        "cpu": _cpu_model(),
        "ram_bytes": _ram_bytes(),
        "gpu": _detect_gpu(),
        "python": python_str,
        "pip": _tool_version("pip", "--version") or _tool_version("pip3", "--version"),
        "uv": _tool_version("uv", "--version"),
        "node": _tool_version("node", "--version"),
        "npm": _tool_version("npm", "--version"),
        "rustc": _tool_version("rustc", "--version"),
        "cargo": _tool_version("cargo", "--version"),
        "java": _tool_version("java", "-version"),
        "go": _tool_version("go", "version"),
        "docker": _tool_version("docker", "--version"),
        "disk_free_bytes": _disk_free_bytes(),
    }
