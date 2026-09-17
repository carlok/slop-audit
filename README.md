# slop-audit

Local multi-tool harness that scores **prose for AI-slop / formulaic style**, general writing issues, descriptive stats, and (separately) **local AI-authorship detector signals**.

Nothing leaves your machine for detection: no hosted detector APIs, no remote LLMs on the target text. Network is only for installs and optional model-weight downloads.

Repository: [github.com/carlok/slop-audit](https://github.com/carlok/slop-audit) (private). Licensed under the [MIT License](LICENSE).

## What you get

| Signal | Meaning |
| --- | --- |
| **Slop Index** | Style / formulaic patterns from linters and slop tools (0–100 + band). |
| **AI-Likeness Ensemble** | Separate authorship-detector scores + agreement. Never merged into Slop Index. |
| **Edits that would lower the Slop Index** | Deterministic, tool-sourced suggestions (quote, rule, tool’s own message). No LLM rewrite prose. |
| **Per-tool matrix** | `OK` / `NOT_RUN` / `ERROR` with exact reasons — failed tools never invent scores. |

Epistemic guardrails:

- **Never** claim the text was “written by AI” (or by a human).
- Prefer concentration language: formulaic/LLM-like patterns + **N of M** local detectors classifying AI-like.
- Density scores on very short pastes (&lt; ~100 words) are advisory only.

## Quick start

```bash
git clone https://github.com/carlok/slop-audit.git
cd slop-audit

# Best-effort install (one failure does not abort the whole install)
bash scripts/install_all.sh

# Put text under audit here (gitignored; never commit your prose)
cp input/README.md input/target.txt   # placeholder smoke only — or write your own into input/target.txt

.venv/bin/python run_audit.py          # skip tools whose cache still matches
.venv/bin/python run_audit.py --force  # re-run everything
```

**Outputs** (all gitignored under a normal run):

| Path | Contents |
| --- | --- |
| `report/report.md`, `report/report.json` | Human-readable + machine-readable audit summary |
| `normalized/results.json` | Normalized per-tool scores and metadata |
| `raw/<tool>/` | Per-tool stdout, stderr, native JSON |

Smoke check (placeholder input only):

```bash
bash scripts/smoke.sh
```

Heavy local ML detectors (e.g. Binoculars, Fast-DetectGPT) may show `NOT_RUN` when available RAM is below their published budgets. That is expected; the rest of the harness still runs.

## Python package

The **distribution / repo** name is `slop-audit` (`pip` / `pyproject.toml`). Import the harness as **`slop_audit`** (for example `from slop_audit.runner import run_audit`). The CLI entrypoint remains `run_audit.py` at the repo root.

## Layout

```text
slop-audit/
  input/            # target.txt (authoritative input; gitignored)
  slop_audit/       # Python package: adapters, scoring, runner, report
  tools/            # local binaries / npm packages
  raw/              # per-tool raw artifacts + cache meta (gitignored)
  normalized/       # results.json (gitignored)
  report/           # report.md / report.json (gitignored)
  logs/             # install/run logs, env, freezes, tool matrix
  scripts/          # install_all.sh, smoke.sh, vale_sync.sh, …
  envs/             # isolated venvs (gitignored)
  vale/             # .vale.ini + custom Slop styles
  run_audit.py      # single entrypoint
```

## Tool families

- **Slop / formulaic style** — dslop, slopscore, ai-slop-detect, slopsift, slop-lint, …
- **Prose / editorial** — Vale (+ write-good / Harper styles), write-good, proselint, LanguageTool (local only), …
- **Stats** — textstat / descriptive metrics
- **Local AI-authorship** — ai-detect, clarity, binoculars, fastdetectgpt (best-effort)

Authoritative readiness table after install/smoke: `logs/tool_matrix.md`.

## Design notes

- One tool failure never aborts the run; adapters catch install/runtime failures and write `STATUS: NOT_RUN` / `ERROR` with a reason.
- Cache key: input SHA + tool version — use `--force` to bypass.
- Spec / plan history (optional reading): `docs/superpowers/`. Release notes: `CHANGELOG.md`.

## Out of scope

- Hosted / cloud detection APIs
- Automatic rewriting of user prose
- Claiming authorship (“written by AI”)

## License

MIT — see [LICENSE](LICENSE). Copyright (c) 2026 Carlo Perassi.
