# Tool READY / NOT_RUN matrix

Generated: 2026-09-13T14:39:10Z (smoke run)
Input SHA-256: 9629185d9de3df5f8433cfff842ae2a728e56448324a6462b9063afc8590c857
Source: `normalized/results.json` after `python run_audit.py --force` on SMOKE_PLACEHOLDER.

READY = adapter returned `OK` on smoke. NOT_RUN = adapter returned `NOT_RUN` or `ERROR` (exact reason below). Scores are never invented for tools that did not succeed.

| ID | Tool | Matrix | Run status | Reason |
|----|------|--------|------------|--------|
| A | `slopscore` (SlopScore) | READY | OK | OK on smoke |
| B | `dslop` (dslop) | READY | OK | OK on smoke |
| C | `slopsift` (SlopSift) | NOT_RUN | ERROR | slopsift: no supported files matched: /workspace/text-audit/.worktrees/feat-text-audit-harness/input/target.txt (use --no-error-on-unmatched-pattern to allow an empty match) |
| D | `ai_slop_detect` (ai-slop-detect) | READY | OK | OK on smoke |
| E | `slop_lint` (slop-lint) | READY | OK | OK on smoke |
| F | `vale` (Vale (+ custom Slop / write-good / Harper packages)) | READY | OK | OK on smoke |
| G | `proselint` (proselint) | READY | OK | OK on smoke |
| H | `write_good` (write-good) | READY | OK | OK on smoke |
| I | `harper` (Harper (via Vale)) | READY | OK | Harper via Vale Harper style package (no direct harper CLI) |
| J | `languagetool` (LanguageTool (local)) | READY | OK | local LanguageTool only (no cloud API) |
| stats | `stats` (textstat + local stats) | READY | OK | descriptive stats only; not used in Slop Index |
| K | `ai_detect` (ai-detect) | READY | OK | AI-likeness = model_ai_pct (mean sentence P(AI)×100) |
| L | `clarity` (Clarity) | READY | OK | Clarity Binoculars-style score: lower = more AI-like |
| M | `binoculars` (Binoculars) | NOT_RUN | NOT_RUN | insufficient memory for Binoculars Falcon-7B×2: MemAvailable=7822761984 < need=21474836480 (20.0 GiB) |
| N | `fastdetectgpt` (Fast-DetectGPT) | NOT_RUN | NOT_RUN | insufficient memory for Fast-DetectGPT gpt-j-6B + gpt-neo-2.7B: MemAvailable=7702364160 < need=15032385536 (14.0 GiB) |

**Counts:** READY=12, NOT_RUN=3, total=15

## Install status (reference)

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
- slopsift ERROR on plain `.txt` (pattern match) → matrix NOT_RUN.

