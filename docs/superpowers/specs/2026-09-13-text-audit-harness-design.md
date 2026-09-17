# Multi-tool local text-audit harness — design

Date: 2026-09-13  
Status: approved for implementation (pending user review of this written spec)

> **Superseded (2026-09-17):** The harness is published on private GitHub as [`carlok/slop-audit`](https://github.com/carlok/slop-audit). SlopPer-style `/workspace/text-audit/` paths and “GitHub repo may come later / out of scope for setup” below reflect the original 2026-09-13 brief only — not current repo policy.

## Goal

Build a reproducible, local-only **operating system** that runs a multi-tool audit of supplied prose for:

1. AI-slop / formulaic writing patterns
2. General prose/style problems
3. Statistical writing characteristics
4. AI-generated-text likelihood signals (separate from style)

The harness lives on SlopPer's computer at `/workspace/text-audit/`. The user pastes text in chat; SlopPer writes it to `input/target.txt`, runs the audit, and returns the report. No sample text is required for setup. A GitHub repo may come later and is out of scope for setup.

## Non-goals

- Hosted detection APIs (GPTZero, Originality.ai, Copyleaks, Pangram, Winston, Sapling, remote LLMs, LanguageTool cloud)
- Claiming “this text was written by AI”
- Rewriting the user’s full text unless explicitly requested
- Creating a GitHub repository during setup
- Inventing scores for tools that failed to install or run

## Constraints

- Prefer local/free/open-source software
- Network OK for installs, clones, and model downloads
- Best-effort heavy ML detectors: install what fits in available RAM/disk; record the rest as `STATUS: NOT RUN` with exact reason
- One tool failure must never abort the experiment
- Record every tool attempted, versions/commits, commands, and failures
- Keep raw tool output
- Distinguish **AI-like style** (Slop Index) from **AI authorship detection** (AI-Likeness Ensemble)
- Treat authorship detectors as noisy classifiers, not proof

## Architecture

### Layout

```text
text-audit/
    input/           # target.txt (authoritative input)
    tools/           # thin adapters (one per tool or tool family)
    raw/             # raw/<tool-name>/* stdout/stderr/native JSON
    normalized/      # results.json (ensemble-ready)
    report/          # report.md, report.json
    logs/            # install.log, run.log, env snapshots, pip freezes
    scripts/         # inspect_env, install_all, helpers
    envs/            # isolated virtualenvs per dependency family
    docs/superpowers/specs/  # this design
    run_audit.py     # single entrypoint
    README.md
```

### Layers

1. **Bootstrap** — environment inspection and best-effort installs; never abort the whole install on one failure.
2. **Runner** — `run_audit.py` orchestrates adapters → normalization → scoring → report.
3. **Adapters** — each tool behind a small wrapper that returns a structured result or `NOT RUN`.

### Restartability

If `raw/<tool>/` already contains a successful result for the same input SHA-256 and tool version, skip recomputation unless `--force` or config change. Incomplete/failed raw dirs may be retried.

## Components

### Environment inspection

Record OS/arch, CPU, RAM, GPU/CUDA/ROCm/MPS, Python, pip, uv, Node/npm, Rust/cargo, Java, Go, Docker (if any), free disk. Prefer uv/venv over system Python mutation.

### Slop-specific tools (A–E)

| ID | Tool | Preferred install |
|----|------|-------------------|
| A | SlopScore | `pip install slopscore-lint` (`jman4162/slopscore`) |
| B | dslop | `pip install dslop` or `uvx` (`aaazzam/dslop`) |
| C | SlopSift / WritingLint | `npx slopsift …` or local npm (`NikhilVerma/writinglint`, package `slopsift`) |
| D | ai-slop-detect | current supported source (`antydizajn/ai-slop-detect`) |
| E | slop-lint | `npx slop-lint …` (`eric-sabe/slop-lint`) |

### General prose linters (F–J)

| ID | Tool | Notes |
|----|------|-------|
| F | Vale | write-good package, Harper if compatible, small transparent custom `Slop` ruleset (generic phrases only; not tuned to fail a specific text) |
| G | proselint | `pip install proselint` |
| H | write-good | `npx write-good` |
| I | Harper | direct CLI if practical; else Vale Harper rules |
| J | LanguageTool | **local** distribution only; skip if disproportionately expensive |

### Statistical baselines (section 4 of prompt)

`textstat` plus local Python for sentence-length distribution, CV, TTR, n-grams, transition/adverb rates, densities per 1k words. Descriptive only — not proof of AI generation.

### AI-authorship detectors (K–N) — separate section

| ID | Tool | Isolation |
|----|------|-----------|
| K | ai-detect (`houtini-ai/ai-detect`) | own venv; DeBERTa preferred unless hardware forces lighter model |
| L | Clarity (`roowus/clarity`) | own venv; Binoculars mode if RAM allows; label lightweight mode if used |
| M | Binoculars (`ahans30/Binoculars`) | own venv; do not substitute arbitrary uncalibrated model pairs |
| N | Fast-DetectGPT (`junchaoIU/fast-detectgpt`) | own venv; published inference path |

Clarity Binoculars mode and original Binoculars are **one method family** for ensemble weighting.

Suggested venvs (create only if install succeeds): `envs/slop`, `envs/prose`, `envs/ml-aidetect`, `envs/ml-clarity`, `envs/ml-binoculars`, `envs/ml-fastdetect`. Save `pip freeze` (or equivalent) per env under `logs/`.

## Data flow

1. Persist input as UTF-8 `input/target.txt` (if a file is supplied later: copy, never modify original).
2. Compute SHA-256, bytes, characters, words, sentences, paragraphs.
3. Run adapters A–N; store raw outputs under `raw/<tool>/`.
4. Normalize deterministic/slop/prose tools into a comparison table.
5. Compute **Slop Index** (style) with prompt weights; renormalize when tools missing — never silent zero.
6. Compute **AI-Likeness Ensemble** separately with family-aware weights.
7. Human editorial analysis runs **only after** automation, and only when real user text is under audit (not during empty setup).
8. Write `report/report.md`, `report/report.json`, `normalized/results.json`.

## Scoring

### Normalization heuristic (tools without native 0–100)

```text
weighted_findings = 3*error_or_high + 2*warning + 1*info
density = weighted_findings / word_count * 1000
normalized = 100 * (1 - exp(-density / 10))
```

State explicitly that this is a heuristic for ensemble comparison, not a probability. Default weight 1 when severity is absent.

### Slop Index (0–100)

Initial weights when all available:

- SlopScore 25%
- dslop 20%
- SlopSift 20%
- ai-slop-detect 10%
- slop-lint 5%
- Vale/custom 10%
- general prose linters (proselint, write-good, Harper, LanguageTool) 10%

Renormalize over successfully executed tools only. Also report **Independent Agreement Count** for substantive phenomena.

Bands: ~0 virtually none; ~25 light; ~50 substantial; ~75 strong; ~100 extreme saturation.

### AI-Likeness Ensemble (0–100)

Not mixed into Slop Index. Convert each detector using documented thresholds/semantics (never assume “higher = more AI” without checking). Family weights:

- DeBERTa/classifier family 40%
- Binoculars/perplexity-ratio family 35%
- Fast-DetectGPT/curvature family 25%

Report disagreement explicitly; disagreement can matter more than the average.

### Epistemic constraint

Strongest allowed conclusion form:

> The text has a high/medium/low concentration of stylistic patterns associated with formulaic or LLM-generated prose, and N of M local authorship detectors classify it as AI-like.

Low detector scores do not establish human authorship.

## Error handling

- Adapter contract: `{ status: OK | NOT_RUN | ERROR, version, commands, raw_paths, native, normalized?, reason? }`
- Install and run logs append-only under `logs/`
- Missing tool → `STATUS: NOT RUN` + reason; no fabricated numeric result
- Opinionated tools (e.g. slop-lint em dashes): single typography hits are weak evidence alone

## Setup “done” criteria

1. Directory tree present
2. Environment inspection logged
3. Best-effort installs completed; READY vs NOT RUN matrix recorded
4. Adapters present for all planned tools (even if backend NOT RUN)
5. Smoke run on a 1–2 sentence placeholder marked `SMOKE_PLACEHOLDER`, then clear or clearly separate from real input
6. Pipeline produces report artifacts without inventing scores for failed tools
7. User notified that paste-in-chat testing can begin

## Operator workflow (post-setup)

1. User pastes text in chat
2. SlopPer writes `input/target.txt`, runs `run_audit.py`
3. SlopPer returns executive result + path/attachment for full `report.md` (and JSON if useful)
4. Optional later: publish tree to GitHub

## Testing during implementation

- Unit-test normalization math and weight renormalization with fixtures
- Adapter dry-run mode that records command lines without requiring every binary
- Smoke placeholder end-to-end for installed tools only

## Implementation sequence (high level)

1. Scaffold tree, README, env inspect, logging helpers
2. Input stats + `run_audit.py` skeleton with adapter interface
3. Install + adapters for deterministic slop tools (A–E)
4. Vale/custom + prose linters (F–J) + textstat
5. Normalization + Slop Index + agreement counts
6. Best-effort ML detectors (K–N) in isolated envs
7. AI-Likeness ensemble + full report templates
8. Smoke run, READY/NOT RUN matrix, handoff to user

Detailed task breakdown belongs in the implementation plan (next step after this spec is reviewed).
