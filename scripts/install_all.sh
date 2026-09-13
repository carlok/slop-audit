#!/usr/bin/env bash
# Best-effort installer for text-audit toolchains.
# Individual failures are recorded; final exit is 0 if this script completes.

set -u
# Do not use set -e — we continue after per-block failures.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
export ROOT

# shellcheck source=install_lib.sh
source "${SCRIPT_DIR}/install_lib.sh"

# Reset status for this run
echo '{"tools": {}}' > "${STATUS_JSON}"
mkdir -p "${LOG_DIR}" "${ROOT}/envs" "${ROOT}/tools"

log_msg "install_all starting ROOT=${ROOT}"
log_msg "python=$(command -v python3) uv=$(command -v uv || echo none) node=$(command -v node || echo none)"

# ---------------------------------------------------------------------------
# A–E + stats/prose Python packages → envs/slop
# ---------------------------------------------------------------------------
install_slop_env() {
  set +e
  local venv="${ROOT}/envs/slop"
  local cmd

  cmd="create_venv ${venv}"
  if ! create_venv "${venv}"; then
    log_fail "envs/slop" "venv creation failed" "${cmd}"
    return 0
  fi

  # Install packages one-by-one so one failure does not block others
  local pkgs=(
    "slopscore-lint"
    "dslop"
    "textstat"
    "proselint"
  )
  local pkg
  for pkg in "${pkgs[@]}"; do
    set +e
    cmd="uv pip install --python ${venv}/bin/python ${pkg}"
    log_msg "CMD: ${cmd}"
    if venv_pip "${venv}" "${pkg}"; then
      log_ok "${pkg}" "${cmd}"
    else
      log_fail "${pkg}" "pip install failed" "${cmd}"
    fi
  done

  # ai-slop-detect from git
  local git_pkg="git+https://github.com/antydizajn/ai-slop-detect.git"
  cmd="uv pip install --python ${venv}/bin/python ${git_pkg}"
  log_msg "CMD: ${cmd}"
  if venv_pip "${venv}" "${git_pkg}"; then
    log_ok "ai-slop-detect" "${cmd}"
  else
    log_fail "ai-slop-detect" "pip install from git failed" "${cmd}"
  fi

  venv_freeze "${venv}" "${LOG_DIR}/pip_freeze_slop.txt"
  if [[ -x "${venv}/bin/python" ]]; then
    log_ok "envs/slop" "create_venv + package installs" "freeze → logs/pip_freeze_slop.txt"
  fi
}

# ---------------------------------------------------------------------------
# Node tools → tools/ (local node_modules)
# ---------------------------------------------------------------------------
install_node_tools() {
  set +e
  local tools_dir="${ROOT}/tools"
  mkdir -p "${tools_dir}"
  local cmd

  if ! command -v npm >/dev/null 2>&1; then
    log_skip "slopsift" "npm not found" "npm install"
    log_skip "slop-lint" "npm not found" "npm install"
    log_skip "write-good" "npm not found" "npm install"
    return 0
  fi

  if [[ ! -f "${tools_dir}/package.json" ]]; then
    cmd="npm init -y (cwd=tools)"
    log_msg "CMD: ${cmd}"
    (cd "${tools_dir}" && npm init -y) >>"${INSTALL_LOG}" 2>&1 || true
  fi

  local pkgs=(slopsift slop-lint write-good)
  local pkg
  for pkg in "${pkgs[@]}"; do
    set +e
    cmd="npm install --prefix ${tools_dir} ${pkg}"
    log_msg "CMD: ${cmd}"
    if (cd "${tools_dir}" && npm install "${pkg}" --save); then
      log_ok "${pkg}" "${cmd}"
    else
      # Runtime may still use npx
      log_fail "${pkg}" "npm install failed; adapters may fall back to npx" "${cmd}"
    fi
  done
}

# ---------------------------------------------------------------------------
# Vale binary → tools/vale/
# ---------------------------------------------------------------------------
install_vale() {
  set +e
  local dest="${ROOT}/tools/vale"
  mkdir -p "${dest}"
  local arch
  arch="$(uname -m)"
  local asset=""
  case "${arch}" in
    x86_64|amd64) asset="Linux_64-bit" ;;
    aarch64|arm64) asset="Linux_arm64" ;;
    *)
      log_skip "vale" "unsupported arch=${arch}" "download vale"
      return 0
      ;;
  esac

  local api_url="https://api.github.com/repos/vale-cli/vale/releases/latest"
  local tag url name
  tag="$(curl -fsSL "${api_url}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tag_name',''))" 2>/dev/null || true)"
  if [[ -z "${tag}" ]]; then
    # Fallback known release
    tag="v3.21.0"
  fi
  local ver="${tag#v}"
  name="vale_${ver}_${asset}.tar.gz"
  url="https://github.com/vale-cli/vale/releases/download/${tag}/${name}"
  # Also try errata-ai mirror path if vale-cli 404s
  local cmd="curl -fsSL ${url} → ${dest}/"
  log_msg "CMD: ${cmd}"
  local tmp
  tmp="$(mktemp -d)"
  if curl -fsSL "${url}" -o "${tmp}/${name}"; then
    tar -xzf "${tmp}/${name}" -C "${tmp}"
    if [[ -f "${tmp}/vale" ]]; then
      mv -f "${tmp}/vale" "${dest}/vale"
      chmod +x "${dest}/vale"
      log_ok "vale" "${cmd}" "installed ${dest}/vale (${tag})"
    else
      log_fail "vale" "archive missing vale binary" "${cmd}"
    fi
  else
    # Fallback to errata-ai
    url="https://github.com/errata-ai/vale/releases/download/${tag}/${name}"
    cmd="curl -fsSL ${url} → ${dest}/"
    log_msg "CMD: fallback ${cmd}"
    if curl -fsSL "${url}" -o "${tmp}/${name}"; then
      tar -xzf "${tmp}/${name}" -C "${tmp}"
      if [[ -f "${tmp}/vale" ]]; then
        mv -f "${tmp}/vale" "${dest}/vale"
        chmod +x "${dest}/vale"
        log_ok "vale" "${cmd}" "installed ${dest}/vale (${tag})"
      else
        log_fail "vale" "archive missing vale binary" "${cmd}"
      fi
    else
      log_fail "vale" "download failed for ${tag}/${name}" "${cmd}"
    fi
  fi
  rm -rf "${tmp}"
}

# ---------------------------------------------------------------------------
# LanguageTool local distribution (best-effort; large zip ~250MB)
# ---------------------------------------------------------------------------
install_languagetool() {
  set +e
  local dest="${ROOT}/tools/languagetool"
  mkdir -p "${dest}"
  if ! command -v java >/dev/null 2>&1; then
    log_skip "languagetool" "java not found" "LanguageTool-stable.zip"
    return 0
  fi
  # Skip if already unpacked
  if compgen -G "${dest}/LanguageTool-*/languagetool-commandline.jar" > /dev/null; then
    log_ok "languagetool" "already present under ${dest}"
    return 0
  fi
  local url="https://languagetool.org/download/LanguageTool-stable.zip"
  local zip="${dest}/LanguageTool-stable.zip"
  local cmd="curl -fL ${url} -o ${zip} && unzip"
  log_msg "CMD: ${cmd}"
  # Guard disk: zip is ~250MB, need headroom
  local disk
  disk="$(disk_free_bytes)"
  if [[ "${disk}" -lt $((1 * 1024 * 1024 * 1024)) ]]; then
    log_skip "languagetool" "disk_free=${disk} < 1GiB for LanguageTool zip" "${cmd}"
    return 0
  fi
  if curl -fL --retry 2 --connect-timeout 30 "${url}" -o "${zip}"; then
    if unzip -q -o "${zip}" -d "${dest}"; then
      rm -f "${zip}"
      if compgen -G "${dest}/LanguageTool-*/languagetool-commandline.jar" > /dev/null; then
        log_ok "languagetool" "${cmd}"
      else
        log_fail "languagetool" "unzip succeeded but jar not found" "${cmd}"
      fi
    else
      log_fail "languagetool" "unzip failed" "${cmd}"
    fi
  else
    log_skip "languagetool" "download failed or unavailable; NOT_RUN" "${cmd}"
  fi
}

# ---------------------------------------------------------------------------
# ML envs (K–N) — one-by-one with RAM/disk guards
# ---------------------------------------------------------------------------
_install_ml_env() {
  local name="$1"       # e.g. ml-aidetect
  local tool_key="$2"   # status key
  local git_url="$3"    # pip git+ URL or empty
  local extra_pkgs="$4" # space-separated extra pip pkgs

  set +e
  local reason
  if ! reason="$(ml_resource_ok)"; then
    # ml_resource_ok prints reason on failure via stdout when we capture wrong —
    # re-check explicitly:
    local mem disk
    mem="$(mem_available_bytes)"
    disk="$(disk_free_bytes)"
    local msg=""
    if [[ "${mem}" -lt $((3 * 1024 * 1024 * 1024)) ]]; then
      msg="MemAvailable=${mem} < 3GiB"
    elif [[ "${disk}" -lt $((5 * 1024 * 1024 * 1024)) ]]; then
      msg="disk_free=${disk} < 5GiB"
    else
      msg="resource guard failed"
    fi
    log_skip "${tool_key}" "${msg}" "ml env ${name}"
    return 0
  fi

  local venv="${ROOT}/envs/${name}"
  local cmd="create_venv ${venv}"
  if ! create_venv "${venv}"; then
    log_fail "${tool_key}" "venv creation failed" "${cmd}"
    return 0
  fi

  # CPU torch first (common dep); tolerate failure and continue
  cmd="uv pip install --python ${venv}/bin/python torch --index-url https://download.pytorch.org/whl/cpu"
  log_msg "CMD: ${cmd}"
  if ! venv_pip "${venv}" torch --index-url https://download.pytorch.org/whl/cpu; then
    log_msg "WARN ${tool_key}: CPU torch install failed; trying default index"
    cmd="uv pip install --python ${venv}/bin/python torch"
    venv_pip "${venv}" torch || log_msg "WARN ${tool_key}: torch still failed"
  fi

  if [[ -n "${extra_pkgs}" ]]; then
    # shellcheck disable=SC2086
    cmd="uv pip install --python ${venv}/bin/python ${extra_pkgs}"
    log_msg "CMD: ${cmd}"
    # shellcheck disable=SC2086
    venv_pip "${venv}" ${extra_pkgs} || log_msg "WARN ${tool_key}: extra pkgs failed"
  fi

  if [[ -n "${git_url}" ]]; then
    cmd="uv pip install --python ${venv}/bin/python ${git_url}"
    log_msg "CMD: ${cmd}"
    if venv_pip "${venv}" "${git_url}"; then
      log_ok "${tool_key}" "${cmd}"
      venv_freeze "${venv}" "${LOG_DIR}/pip_freeze_${name}.txt"
    else
      # Clone + editable install fallback
      local clone_dir="${ROOT}/envs/src/${name}"
      mkdir -p "$(dirname "${clone_dir}")"
      local repo="${git_url#git+}"
      repo="${repo%.git}"
      cmd="git clone --depth 1 ${repo} ${clone_dir} && pip install -e ."
      log_msg "CMD: fallback ${cmd}"
      rm -rf "${clone_dir}"
      if git clone --depth 1 "${repo}" "${clone_dir}" \
        && venv_pip "${venv}" -e "${clone_dir}"; then
        log_ok "${tool_key}" "${cmd}"
        venv_freeze "${venv}" "${LOG_DIR}/pip_freeze_${name}.txt"
      else
        log_fail "${tool_key}" "git pip and clone install failed" "${cmd}"
      fi
    fi
  else
    log_ok "${tool_key}" "venv ${venv} created (no git package)"
    venv_freeze "${venv}" "${LOG_DIR}/pip_freeze_${name}.txt"
  fi
}

install_binoculars() {
  set +e
  local tool_key="binoculars"
  local name="ml-binoculars"
  local mem disk
  mem="$(mem_available_bytes)"
  disk="$(disk_free_bytes)"
  if [[ "${mem}" -lt $((3 * 1024 * 1024 * 1024)) ]]; then
    log_skip "${tool_key}" "MemAvailable=${mem} < 3GiB" "ml env ${name}"
    return 0
  fi
  if [[ "${disk}" -lt $((5 * 1024 * 1024 * 1024)) ]]; then
    log_skip "${tool_key}" "disk_free=${disk} < 5GiB" "ml env ${name}"
    return 0
  fi
  local venv="${ROOT}/envs/${name}"
  create_venv "${venv}" || { log_fail "${tool_key}" "venv creation failed"; return 0; }
  venv_pip "${venv}" torch --index-url https://download.pytorch.org/whl/cpu \
    || venv_pip "${venv}" torch || true
  # Prefer modern transformers (pinned 4.31 in upstream requires ancient tokenizers/rustc)
  local cmd="clone Binoculars + pip install -e . --no-deps + modern transformers"
  log_msg "CMD: ${cmd}"
  local clone_dir="${ROOT}/envs/src/${name}"
  rm -rf "${clone_dir}"
  if git clone --depth 1 https://github.com/ahans30/Binoculars.git "${clone_dir}" \
    && venv_pip "${venv}" transformers accelerate datasets numpy scikit-learn pandas sentencepiece \
    && venv_pip "${venv}" -e "${clone_dir}" --no-deps; then
    log_ok "${tool_key}" "${cmd}" "installed with modern transformers (upstream pin skipped)"
    venv_freeze "${venv}" "${LOG_DIR}/pip_freeze_${name}.txt"
  else
    log_fail "${tool_key}" "clone or no-deps install failed" "${cmd}"
  fi
}

install_fastdetect() {
  set +e
  local tool_key="fastdetectgpt"
  local name="ml-fastdetect"
  local mem disk
  mem="$(mem_available_bytes)"
  disk="$(disk_free_bytes)"
  if [[ "${mem}" -lt $((3 * 1024 * 1024 * 1024)) ]]; then
    log_skip "${tool_key}" "MemAvailable=${mem} < 3GiB" "ml env ${name}"
    return 0
  fi
  if [[ "${disk}" -lt $((5 * 1024 * 1024 * 1024)) ]]; then
    log_skip "${tool_key}" "disk_free=${disk} < 5GiB" "ml env ${name}"
    return 0
  fi
  local venv="${ROOT}/envs/${name}"
  create_venv "${venv}" || { log_fail "${tool_key}" "venv creation failed"; return 0; }
  venv_pip "${venv}" torch --index-url https://download.pytorch.org/whl/cpu \
    || venv_pip "${venv}" torch || true
  local clone_dir="${ROOT}/envs/src/${name}"
  local cmd="git clone fast-detectgpt + pip install requirements (no setup.py)"
  log_msg "CMD: ${cmd}"
  rm -rf "${clone_dir}"
  if ! git clone --depth 1 https://github.com/junchaoIU/fast-detectgpt.git "${clone_dir}"; then
    log_fail "${tool_key}" "git clone failed" "${cmd}"
    return 0
  fi
  # Install deps from requirements, skipping openai (hosted API) and pinning conflicts
  if [[ -f "${clone_dir}/requirements.txt" ]]; then
    # Filter openai; install rest best-effort
    local req_filtered
    req_filtered="$(mktemp)"
    grep -viE '^(openai|matplotlib)($|[=<>])' "${clone_dir}/requirements.txt" > "${req_filtered}" || true
    venv_pip "${venv}" -r "${req_filtered}" || venv_pip "${venv}" transformers datasets numpy tqdm sentencepiece nltk || true
    rm -f "${req_filtered}"
  else
    venv_pip "${venv}" transformers datasets numpy tqdm sentencepiece || true
  fi
  # Repo is scripts-only; READY if import torch+transformers works and clone exists
  if "${venv}/bin/python" -c "import torch, transformers" 2>/dev/null \
    && [[ -d "${clone_dir}" ]]; then
    log_ok "${tool_key}" "${cmd}" "venv+deps+clone ready (script repo, no pip package)"
    venv_freeze "${venv}" "${LOG_DIR}/pip_freeze_${name}.txt"
  else
    log_fail "${tool_key}" "torch/transformers import or clone missing" "${cmd}"
  fi
}

install_ml_envs() {
  set +e
  # K ai-detect
  _install_ml_env "ml-aidetect" "ai-detect" \
    "git+https://github.com/houtini-ai/ai-detect.git" \
    "transformers accelerate sentencepiece"
  # L Clarity
  _install_ml_env "ml-clarity" "clarity" \
    "git+https://github.com/roowus/clarity.git" \
    "transformers accelerate"
  # M Binoculars (special: upstream pins ancient transformers)
  install_binoculars
  # N Fast-DetectGPT (special: no setup.py)
  install_fastdetect
}

# ---------------------------------------------------------------------------
# Run all blocks
# ---------------------------------------------------------------------------
run_block "slop_env" install_slop_env
run_block "node_tools" install_node_tools
run_block "vale" install_vale
run_block "languagetool" install_languagetool
run_block "ml_envs" install_ml_envs

# Summarize
python3 - "${STATUS_JSON}" <<'PY'
import json, sys
from pathlib import Path
p = Path(sys.argv[1])
data = json.loads(p.read_text(encoding="utf-8"))
tools = data.get("tools") or {}
ok = sum(1 for t in tools.values() if t.get("status") == "OK")
fail = sum(1 for t in tools.values() if t.get("status") == "FAIL")
skip = sum(1 for t in tools.values() if t.get("status") in ("NOT_RUN", "SKIPPED"))
print(f"install_all summary: OK={ok} FAIL={fail} NOT_RUN={skip} total={len(tools)}")
data["summary"] = {"OK": ok, "FAIL": fail, "NOT_RUN": skip, "total": len(tools)}
p.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

log_msg "install_all completed (best-effort; exit 0)"
exit 0
