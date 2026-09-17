# slop-audit Phase 1 (docs & packaging) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make private `carlok/slop-audit` look finished and cloneable: MIT LICENSE, polished README, pyproject metadata, CHANGELOG 0.1.0, light docs cleanup — without renaming the Python package.

**Architecture:** Docs/metadata-only PR. No adapter or scoring behavior changes. Import package stays `text_audit` until Phase 2.

**Tech Stack:** Markdown, MIT license text, PEP 621 `pyproject.toml`, existing pytest suite.

## Global Constraints

- Repo: `https://github.com/carlok/slop-audit` (private)
- Spec: `docs/superpowers/specs/2026-09-17-slop-audit-brush-up-design.md`
- LICENSE copyright: **Carlo Perassi**, year **2026**, MIT
- Do **not** rename `text_audit` → `slop_audit` in this PR
- Do **not** commit `input/target.txt`, `report/`, or user sample prose
- Do **not** add heavy BERT-class detectors
- Epistemic rules unchanged
- Existing tests must stay green (`pytest`)

---

### Task 1: LICENSE + CHANGELOG + pyproject metadata

**Files:**
- Create: `LICENSE`
- Create: `CHANGELOG.md`
- Modify: `pyproject.toml`
- Modify: `docs/superpowers/specs/2026-09-17-slop-audit-brush-up-design.md` (status already approved; leave unless stale)

**Interfaces:**
- Consumes: approved author line Carlo Perassi / 2026
- Produces: MIT `LICENSE`; `CHANGELOG.md` with `## [0.1.0]` describing harness as shipped; `pyproject.toml` with `description`, `readme = "README.md"`, authors, and project URLs pointing at the GitHub repo

- [ ] **Step 1:** Add MIT `LICENSE` with copyright `Copyright (c) 2026 Carlo Perassi`
- [ ] **Step 2:** Add `CHANGELOG.md` with `[0.1.0]` — local multi-tool slop/prose/stats/AI-likeness harness; Slop Index edit suggestions; private GitHub publication
- [ ] **Step 3:** Extend `pyproject.toml` (keep `name = "slop-audit"`, `requires-python = ">=3.11"`) with description, readme, authors, urls (Homepage / Repository → `https://github.com/carlok/slop-audit`)
- [ ] **Step 4:** Run `pytest -q` — expect green
- [ ] **Step 5:** Commit `chore: add MIT license, changelog, and pyproject metadata`

---

### Task 2: README polish + light docs cleanup

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-09-13-text-audit-harness-design.md` (short superseded note only)
- Modify: `docs/superpowers/plans/2026-09-13-text-audit-harness.md` only if it still claims GitHub is out of scope (short note, do not rewrite history)

**Interfaces:**
- Consumes: live private repo URL; Phase 2 rename deferred
- Produces: README a stranger can follow; no contradictory “GitHub later” framing

- [ ] **Step 1:** Rewrite/polish `README.md`:
  - Title `slop-audit`
  - Clone: `git clone https://github.com/carlok/slop-audit.git`
  - Install → put text in `input/target.txt` → `run_audit.py` → outputs
  - Explicit note: Python import package is still `text_audit` until Phase 2
  - Keep epistemic rules, layout, out-of-scope (hosted APIs / rewrite / authorship claims)
  - Mention LICENSE (MIT)
  - Remove or fix wording that says GitHub publication is out of scope or that the harness only lives on `/workspace/text-audit/`
- [ ] **Step 2:** In `2026-09-13-text-audit-harness-design.md`, add a short note near the top that GitHub publication is superseded by private `carlok/slop-audit`; do not rewrite the original design body
- [ ] **Step 3:** Same light note on the old plan if needed
- [ ] **Step 4:** `pytest -q` still green
- [ ] **Step 5:** Commit `docs: polish README and mark GitHub publication as done`
- [ ] **Step 6:** Open PR targeting default branch (`master`); title/body summarize Phase 1 only

---

## Done when

- PR open with LICENSE, CHANGELOG, pyproject metadata, polished README, light historical-doc notes
- Tests green
- No package rename; no sample text; no heavy detectors
