# text-audit

Local-only multi-tool harness for auditing prose: AI-slop / formulaic style, general prose issues, descriptive stats, and (separately) local AI-authorship detector signals.

Never sends target text to hosted detection APIs or remote LLMs.

## Layout

```text
text-audit/
  input/            # target.txt (authoritative input; paste replaces this file)
  text_audit/       # package: adapters, scoring, runner, report
  tools/            # local binaries / npm packages (vale, languagetool, node_modules)
  raw/              # raw/<tool>/* stdout/stderr/native JSON + cache meta
  normalized/       # results.json
  report/           # report.md, report.json
  logs/             # install.log, run.log, env, pip freezes, tool_matrix.md (+ .smoke.md)
  scripts/          # install_all.sh, smoke.sh, inspect_env.py, helpers
  envs/             # isolated venvs per dependency family (gitignored)
  vale/             # .vale.ini + custom Slop styles
  run_audit.py      # single entrypoint
```

## Install

Best-effort (one failure does not abort the whole install):

```bash
bash scripts/install_all.sh
```

Prefer the project `.venv` or tool-specific `envs/*` venvs. Recorded status: `logs/install_status.json`, freezes under `logs/pip_freeze_*.txt`.

## Run

1. Put text in `input/target.txt` (see `input/README.md`).
2. Run:

```bash
python run_audit.py          # skip tools whose raw cache matches input SHA + version
python run_audit.py --force  # re-run everything
```

Or with the worktree venv:

```bash
.venv/bin/python run_audit.py --force
```

Outputs: `report/report.md`, `report/report.json`, `normalized/results.json`, `raw/<tool>/`.

Smoke (placeholder only):

```bash
bash scripts/smoke.sh
```

## Epistemic rules

- **Never** conclude the text was “written by AI” (or by a human).
- Use concentration language for style (Slop Index band) plus **N of M** local authorship detectors.
- Keep **Slop Index** (style / formulaic patterns) separate from **AI-Likeness Ensemble** (authorship detectors).
- Do not invent scores for tools that did not run; use `STATUS: NOT_RUN` or `ERROR` with the exact reason.
- One tool failure must not abort the run.

## Operator flow (paste-in-chat)

1. User pastes the sentence/paragraph in chat.
2. Operator writes it to `input/target.txt`.
3. Operator runs `python run_audit.py` (or `--force`).
4. Operator returns `report/report.md` (and notes any `NOT_RUN` tools from the matrix).
5. Setup handoff: after smoke, clear `target.txt` to `# paste target text here` and ask the user for real text.

## Tool matrix

- **Authoritative handoff:** `logs/tool_matrix.md` (includes install-status reference, friendly names, epistemic / ML notes).
- **Smoke refresh:** `scripts/smoke.sh` writes the thin READY table to `logs/tool_matrix.smoke.md` and does **not** overwrite the handoff matrix.

Heavy ML detectors may be `NOT_RUN` when RAM is below published model budgets.

## Density / short text

Heuristic density uses denominator `max(word_count, 100)` before the published formula  
`score = 100 * (1 - exp(-density/10))` where `density = weighted_findings / denom * 1000`.  
Density scores are **unreliable on very short texts** (below ~100 words); treat bands as advisory only for short pastes.

## Known gaps

- **Independent Agreement / corroborated rows:** `independent_agreement` helper and report section exist, but live runs do not yet extract shared finding labels from adapter natives into corroborated phenomena (always empty until a post-pass is wired).

## Constraints (summary)

- Local / free / open-source preferred; network OK for installs and model weight downloads only.
- LanguageTool: local distribution only (no cloud API).
- GitHub publication is out of scope for setup.
