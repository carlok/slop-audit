#!/usr/bin/env bash
# Download Vale Packages (write-good, Harper) into vale/styles/ (gitignored).
# Custom Slop rules under vale/styles/Slop/ are tracked and left untouched.
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VALE_BIN="${ROOT}/tools/vale/vale"
CONFIG="${ROOT}/vale/.vale.ini"

if [[ ! -x "${VALE_BIN}" ]]; then
  # Fall back to PATH vale if local binary missing
  if command -v vale >/dev/null 2>&1; then
    VALE_BIN="$(command -v vale)"
  else
    echo "vale_sync: vale binary not found at ${ROOT}/tools/vale/vale (and not on PATH)" >&2
    exit 1
  fi
fi

if [[ ! -f "${CONFIG}" ]]; then
  echo "vale_sync: missing config ${CONFIG}" >&2
  exit 1
fi

echo "vale_sync: ${VALE_BIN} --config=${CONFIG} sync"
exec "${VALE_BIN}" --config="${CONFIG}" sync
