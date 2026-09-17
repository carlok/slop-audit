# slop-audit Phase 2 (code hygiene) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the import package `text_audit` → `slop_audit`, wire live independent-agreement / corroborated findings into reports, and drop stale worktree path wording.

**Architecture:** Mechanical package rename with import/test updates; then a runner post-pass that extracts shared finding labels from OK tool natives into a phenomena map, feeds `independent_agreement()`, and populates the report’s corroborated section (today always empty). Docs catch up to the new import name.

**Tech Stack:** Python 3.11+, existing pytest suite, existing `agreement.independent_agreement`.

## Global Constraints

- Repo: `https://github.com/carlok/slop-audit` (private); base branch: latest `master` (Phase 1 already merged)
- Spec: `docs/superpowers/specs/2026-09-17-slop-audit-brush-up-design.md` Phase 2
- Do **not** add heavy BERT-class detectors
- Do **not** commit `input/target.txt`, `report/`, or user sample prose
- Epistemic rules unchanged
- Keep `pytest` green; add tests for agreement extraction
- Entry point may remain `run_audit.py` (script name OK); package import must be `slop_audit`

---

### Task 1: Rename package `text_audit` → `slop_audit`

**Files:**
- Rename/move: `text_audit/` → `slop_audit/`
- Modify: all imports in package, `run_audit.py`, `tests/**`, scripts/docs that teach `import text_audit`
- Modify: `README.md` (remove “still text_audit until Phase 2”; say `slop_audit`)
- Modify: `CHANGELOG.md` — add Unreleased / 0.2.0 note for the rename

**Interfaces:**
- Consumes: current package layout
- Produces: `import slop_audit` works; no remaining `text_audit` imports in code/tests

- [ ] **Step 1:** Rename directory; update every `from text_audit` / `import text_audit`
- [ ] **Step 2:** Update README / CHANGELOG / any install docs that mention the old import
- [ ] **Step 3:** `pytest -q` green
- [ ] **Step 4:** Commit `refactor: rename text_audit package to slop_audit`

---

### Task 2: Wire live independent-agreement / corroborated findings

**Files:**
- Modify: `slop_audit/runner.py` (today passes `corroborated=[]`)
- Possibly add: `slop_audit/phenomena.py` or helpers next to `agreement.py` for extracting labels from adapter natives
- Modify: `slop_audit/report.py` only if needed for display
- Test: `tests/test_agreement.py` and/or new `tests/test_phenomena.py`

**Interfaces:**
- Consumes: `independent_agreement(phenomena: dict[str, list[str]]) -> list[dict]` in `agreement.py`
- Produces: runner builds `phenomena` from OK tool results (shared finding labels → list of tool names); passes non-empty corroborated list into the report when ≥2 tools share a label; empty only when nothing corroborates

- [ ] **Step 1:** Write failing tests: two tools sharing a label → corroborated row; single-tool label → not corroborated; AI-authorship tools excluded or clearly separated per existing epistemic split (prefer style/slop/prose tools for Slop-facing corroboration — verify design intent and match report section purpose)
- [ ] **Step 2:** Implement extraction from natives (Vale Check/Match, write-good quotes, dslop rules, etc. — best-effort, documented) and call `independent_agreement` from the runner
- [ ] **Step 3:** Ensure report section shows real rows; still shows empty placeholder when none
- [ ] **Step 4:** `pytest -q` green
- [ ] **Step 5:** Commit `feat: wire live independent-agreement into audit reports`

---

### Task 3: Drop stale worktree / path wording

**Files:**
- Modify: `logs/tool_matrix.md` and/or install docs / README if they still mention `.worktrees/feat-text-audit-harness` or obsolete `/workspace/text-audit` as the only home
- Grep the tree for `worktrees/feat-text-audit` and `text_audit` leftovers in user-facing docs

- [ ] **Step 1:** Grep and clean stale paths in tracked docs (do not rewrite historical design body beyond a short note if already present)
- [ ] **Step 2:** `pytest -q` green
- [ ] **Step 3:** Commit `docs: drop stale worktree path references`
- [ ] **Step 4:** Open PR to `master` summarizing Phase 2

---

## Done when

- PR open: package is `slop_audit`, corroborated findings can populate, stale worktree wording gone
- Tests green including new agreement/phenomena tests
- No heavy detectors; no sample prose
