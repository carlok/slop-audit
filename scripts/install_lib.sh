#!/usr/bin/env bash
# Shared helpers for best-effort toolchain installs.
# Sourced by scripts/install_all.sh — do not execute directly.

: "${ROOT:?ROOT must be set before sourcing install_lib.sh}"

LOG_DIR="${ROOT}/logs"
STATUS_JSON="${LOG_DIR}/install_status.json"
INSTALL_LOG="${LOG_DIR}/install.log"

mkdir -p "${LOG_DIR}"

# Initialize status JSON object if missing
if [[ ! -f "${STATUS_JSON}" ]]; then
  echo '{}' > "${STATUS_JSON}"
fi

_timestamp() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }

log_msg() {
  # stdout only — caller should tee to logs/install.log
  printf '[%s] %s\n' "$(_timestamp)" "$*"
}

# record_status TOOL STATUS REASON [COMMAND]
# STATUS: OK | FAIL | NOT_RUN | SKIPPED
record_status() {
  local tool="$1"
  local status="$2"
  local reason="${3:-}"
  local command="${4:-}"
  python3 - "$STATUS_JSON" "$tool" "$status" "$reason" "$command" <<'PY'
import json, sys
from pathlib import Path
import datetime
path, tool, status, reason, command = sys.argv[1:6]
p = Path(path)
try:
    data = json.loads(p.read_text(encoding="utf-8") or "{}")
except Exception:
    data = {}
if not isinstance(data, dict):
    data = {}
tools = data.setdefault("tools", {})
tools[tool] = {
    "status": status,
    "reason": reason,
    "command": command,
}
data["updated_at"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
p.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
}

log_ok() {
  local tool="$1"
  local command="${2:-}"
  local reason="${3:-}"
  log_msg "OK  ${tool}${command:+ — ${command}}"
  record_status "${tool}" "OK" "${reason}" "${command}"
}

log_fail() {
  local tool="$1"
  local reason="${2:-failed}"
  local command="${3:-}"
  log_msg "FAIL ${tool}: ${reason}${command:+ — ${command}}"
  record_status "${tool}" "FAIL" "${reason}" "${command}"
}

log_skip() {
  local tool="$1"
  local reason="${2:-skipped}"
  local command="${3:-}"
  log_msg "SKIP ${tool}: ${reason}"
  record_status "${tool}" "NOT_RUN" "${reason}" "${command}"
}

# Prefer uv venv, else python -m venv
create_venv() {
  local venv_path="$1"
  mkdir -p "$(dirname "${venv_path}")"
  if [[ -d "${venv_path}" && -x "${venv_path}/bin/python" ]]; then
    log_msg "venv exists: ${venv_path}"
    return 0
  fi
  if command -v uv >/dev/null 2>&1; then
    log_msg "create_venv: uv venv ${venv_path}"
    uv venv "${venv_path}"
  else
    log_msg "create_venv: python -m venv ${venv_path}"
    python3 -m venv "${venv_path}"
  fi
}

venv_pip() {
  local venv_path="$1"
  shift
  if command -v uv >/dev/null 2>&1; then
    uv pip install --python "${venv_path}/bin/python" "$@"
  else
    "${venv_path}/bin/python" -m pip install "$@"
  fi
}

venv_freeze() {
  local venv_path="$1"
  local out="$2"
  if [[ -x "${venv_path}/bin/python" ]]; then
    if command -v uv >/dev/null 2>&1; then
      uv pip freeze --python "${venv_path}/bin/python" > "${out}" 2>/dev/null || true
    else
      "${venv_path}/bin/python" -m pip freeze > "${out}" 2>/dev/null || true
    fi
  fi
}

# MemAvailable in bytes (from /proc/meminfo)
mem_available_bytes() {
  awk '/MemAvailable:/ {print $2 * 1024; exit}' /proc/meminfo 2>/dev/null || echo 0
}

disk_free_bytes() {
  python3 -c "import shutil; print(shutil.disk_usage('${ROOT}').free)"
}

# Returns 0 if OK to proceed with ML install/model pull; 1 if should skip
# Thresholds: MemAvailable >= 3GiB and disk_free >= 5GiB
ml_resource_ok() {
  local mem disk
  mem="$(mem_available_bytes)"
  disk="$(disk_free_bytes)"
  local need_mem=$((3 * 1024 * 1024 * 1024))
  local need_disk=$((5 * 1024 * 1024 * 1024))
  if [[ "${mem}" -lt "${need_mem}" ]]; then
    echo "MemAvailable=${mem} < 3GiB"
    return 1
  fi
  if [[ "${disk}" -lt "${need_disk}" ]]; then
    echo "disk_free=${disk} < 5GiB"
    return 1
  fi
  return 0
}

# Run a named install block without aborting the parent script.
# Usage: run_block NAME bash-code-as-string  OR use a function name
run_block() {
  local name="$1"
  shift
  set +e
  log_msg "=== BEGIN ${name} ==="
  "$@"
  local rc=$?
  log_msg "=== END ${name} (rc=${rc}) ==="
  set +e
  return 0
}
