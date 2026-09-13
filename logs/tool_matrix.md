# Tool READY / NOT_RUN matrix

Generated: 2026-09-13T14:53:40Z (post-fix smoke)
Input SHA-256: 9629185d9de3df5f8433cfff842ae2a728e56448324a6462b9063afc8590c857
Source: `normalized/results.json` after `python run_audit.py --force` on SMOKE_PLACEHOLDER.

READY = adapter returned `OK` on smoke. NOT_RUN = adapter returned `NOT_RUN` or `ERROR` (exact reason below). Scores are never invented for tools that did not succeed.

Thin smoke refresh only: `logs/tool_matrix.smoke.md`. This file is the authoritative handoff matrix (install + notes).

| ID | Tool | Matrix | Run status | Reason |
|----|------|--------|------------|--------|
| A | `slopscore` (SlopScore) | READY | OK | OK on smoke |
| B | `dslop` (dslop) | READY | OK | OK on smoke |
| C | `slopsift` (SlopSift) | READY | OK | OK on smoke |
| D | `ai_slop_detect` (ai-slop-detect) | READY | OK | OK on smoke |
| E | `slop_lint` (slop-lint) | READY | OK | OK on smoke |
| F | `vale` (Vale (+ custom Slop / write-good / Harper packages)) | READY | OK | OK on smoke |
| G | `proselint` (proselint) | READY | OK | OK on smoke |
| H | `write_good` (write-good) | READY | OK | OK on smoke |
| I | `harper` (Harper (via Vale)) | READY | OK | Harper via Vale Harper style package (no direct harper CLI) |
| J | `languagetool` (LanguageTool (local)) | READY | OK | local LanguageTool only (no cloud API) |
| stats | `stats` (textstat + local stats) | READY | OK | descriptive stats only; not used in Slop Index |
| K | `ai_detect` (ai-detect) | READY | OK | AI-likeness = model_ai_pct (mean sentence P(AI)×100). Thresholds: >50 LIKELY AI, <40 LIKELY HUMAN, else MIXED (ai_detect.detector.verdict). Sentence label AI if ai_prob>=0.5. Local weights only; never hosted detection APIs. model=desklib. |
| L | `clarity` (Clarity) | READY | OK | Clarity Binoculars-style score: lower = more AI-like. Labels: score < threshold_low → ai; score > threshold_high → human; else uncertain (defaults binoculars low=0.905 high=1.11; fast mode uses FAST_THRESHOLD_*). AI-likeness mapped linearly so score=low → 100, score=high → 0 (clamp 0–100). Local HF causal LMs only; never hosted detection APIs. mode=binoculars. |
| M | `binoculars` (Binoculars) | NOT_RUN | NOT_RUN | insufficient memory for Binoculars Falcon-7B×2: MemAvailable=14342844416 < need=21474836480 (20.0 GiB) |
| N | `fastdetectgpt` (Fast-DetectGPT) | NOT_RUN | NOT_RUN | insufficient memory for Fast-DetectGPT gpt-j-6B + gpt-neo-2.7B: MemAvailable=14259302400 < need=15032385536 (14.0 GiB) |

**Counts:** READY=13, NOT_RUN=2, total=15

## Install status (reference)
 (reference)

From `logs/install_status.json` (best-effort; install OK ≠ runtime READY for heavy ML).

- `ai-detect`: OK — uv pip install --python /workspace/text-audit/.worktrees/feat-text-audit-harness/envs/ml-aidetect/bi
- `ai-slop-detect`: OK — uv pip install --python /workspace/text-audit/.worktrees/feat-text-audit-harness/envs/slop/bin/pytho
- `binoculars`: OK — installed with modern transformers (upstream pin skipped)
- `clarity`: OK — uv pip install --python /workspace/text-audit/.worktrees/feat-text-audit-harness/envs/ml-clarity/bin
- `dslop`: OK — uv pip install --python /workspace/text-audit/.worktrees/feat-text-audit-harness/envs/slop/bin/pytho
- `envs/slop`: OK — freeze → logs/pip_freeze_slop.txt
- `fastdetectgpt`: OK — venv+deps+clone ready (script repo, no pip package)
- `languagetool`: OK — already present under /workspace/text-audit/.worktrees/feat-text-audit-harness/tools/languagetool
- `proselint`: OK — uv pip install --python /workspace/text-audit/.worktrees/feat-text-audit-harness/envs/slop/bin/pytho
- `slop-lint`: OK — npm install --prefix /workspace/text-audit/.worktrees/feat-text-audit-harness/tools slop-lint
- `slopscore-lint`: OK — uv pip install --python /workspace/text-audit/.worktrees/feat-text-audit-harness/envs/slop/bin/pytho
- `slopsift`: OK — npm install --prefix /workspace/text-audit/.worktrees/feat-text-audit-harness/tools slopsift
- `textstat`: OK — uv pip install --python /workspace/text-audit/.worktrees/feat-text-audit-harness/envs/slop/bin/pytho
- `vale`: OK — installed /workspace/text-audit/.worktrees/feat-text-audit-harness/tools/vale/vale (v3.21.0)
- `write-good`: OK — npm install --prefix /workspace/text-audit/.worktrees/feat-text-audit-harness/tools write-good

## Notes

- Slop Index and AI-Likeness Ensemble are separate.
- Epistemic: never conclude text was "written by AI"; use concentration + N of M detectors form.
- Heavy ML (binoculars, fastdetectgpt) correctly NOT_RUN when MemAvailable < published model budgets.
- slopsift: `--no-ignore` + `--no-error-on-unmatched-pattern` so gitignored `input/target.txt` is linted; pure unmatched-pattern failures map to NOT_RUN.
- Smoke refresh writes `logs/tool_matrix.smoke.md` (does not overwrite this handoff file).

