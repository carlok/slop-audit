#!/usr/bin/env bash
# Smoke-run the text-audit harness with a fixed placeholder (not real user text).
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${ROOT}"

mkdir -p input logs
SMOKE_TEXT='SMOKE_PLACEHOLDER: The quick brown fox jumps over the lazy dog. This second sentence exists only to exercise the audit pipeline.'
printf '%s\n' "${SMOKE_TEXT}" > input/target.txt

PY="${ROOT}/.venv/bin/python"
if [[ ! -x "${PY}" ]]; then
  PY="python3"
  export PYTHONPATH="${ROOT}${PYTHONPATH:+:${PYTHONPATH}}"
fi

echo "Smoke: running ${PY} run_audit.py --force"
"${PY}" run_audit.py --force
rc=$?

# Refresh tool matrix from normalized results when present
if [[ -f normalized/results.json ]]; then
  "${PY}" - << 'PY'
import json
from datetime import datetime, timezone
from pathlib import Path
ROOT = Path(".")
results = json.loads((ROOT / "normalized/results.json").read_text())
planned = [
    ("A", "slopscore"), ("B", "dslop"), ("C", "slopsift"), ("D", "ai_slop_detect"),
    ("E", "slop_lint"), ("F", "vale"), ("G", "proselint"), ("H", "write_good"),
    ("I", "harper"), ("J", "languagetool"), ("stats", "stats"),
    ("K", "ai_detect"), ("L", "clarity"), ("M", "binoculars"), ("N", "fastdetectgpt"),
]
by = {t["tool"]: t for t in results["tools"]}
ready = not_run = 0
lines = [
    "# Tool READY / NOT_RUN matrix",
    "",
    f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')} (smoke.sh)",
    f"Input SHA-256: {results['input']['sha256']}",
    "",
    "| ID | Tool | Matrix | Run status | Reason |",
    "|----|------|--------|------------|--------|",
]
for id_, key in planned:
    t = by.get(key, {})
    status = t.get("status", "NOT_RUN")
    reason = (t.get("reason") or t.get("notes") or status).replace("|", "\\|")
    if status == "OK":
        matrix = "READY"
        ready += 1
    else:
        matrix = "NOT_RUN"
        not_run += 1
    lines.append(f"| {id_} | `{key}` | {matrix} | {status} | {reason} |")
lines += ["", f"**Counts:** READY={ready}, NOT_RUN={not_run}, total={ready+not_run}", ""]
(ROOT / "logs/tool_matrix.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"Wrote logs/tool_matrix.md READY={ready} NOT_RUN={not_run}")
PY
fi

# Clear authoritative input so real pastes are not confused with smoke
printf '%s\n' '# paste target text here' > input/target.txt
echo "Cleared input/target.txt → '# paste target text here'"
echo "Report: ${ROOT}/report/report.md"
exit "${rc}"
