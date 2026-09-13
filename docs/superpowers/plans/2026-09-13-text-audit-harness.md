# Text-Audit Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local multi-tool text-audit orchestrator at `/workspace/text-audit` that installs what it can, runs adapters A–N best-effort, and produces Slop Index + separate AI-Likeness reports without fabricating missing-tool scores.

**Architecture:** Thin tool adapters return a shared `ToolResult` dataclass; `run_audit.py` orchestrates inspect → input stats → adapters → normalize → score → `report.md`/`report.json`. Isolated venvs under `envs/`; raw outputs under `raw/<tool>/`; restartable by input SHA + tool version.

**Tech Stack:** Python 3.13, uv/venv, pytest, Node/npx for JS linters, Vale, optional local LanguageTool + PyTorch detectors.

## Global Constraints

- Root path: `/workspace/text-audit`
- Never send target text to hosted detection APIs or remote LLMs
- One tool failure must not abort the run; use `STATUS: NOT_RUN` or `ERROR` with exact reason
- Never invent scores for tools that did not run
- Keep Slop Index separate from AI-Likeness Ensemble
- Best-effort ML: install what fits RAM/disk; otherwise `NOT_RUN`
- Epistemic: never conclude "written by AI"; use concentration + N of M detectors form
- Prefer uv/venv; record versions/commands in `logs/`
- TDD: failing test → implement → pass → commit per task
- User drives tests by pasting text in chat after setup handoff

## File Structure

```text
text-audit/
  run_audit.py
  README.md
  pyproject.toml                 # pytest + package metadata for text_audit
  text_audit/
    __init__.py
    models.py                    # ToolResult, InputStats, EnvironmentInfo
    logging_util.py              # append-only install/run logs
    env_inspect.py
    input_stats.py
    normalize.py                 # density → normalized 0–100
    weights.py                   # renormalize missing tools
    scoring_slop.py
    scoring_ai.py
    agreement.py
    report.py
    runner.py                    # orchestration + restartability
    adapters/
      __init__.py                # registry list
      base.py                    # run_subprocess helpers
      slopscore.py
      dslop_adapter.py
      slopsift.py
      ai_slop_detect.py
      slop_lint.py
      vale_adapter.py
      proselint_adapter.py
      write_good.py
      harper_adapter.py
      languagetool_adapter.py
      stats_adapter.py
      ai_detect.py
      clarity_adapter.py
      binoculars_adapter.py
      fastdetectgpt_adapter.py
  scripts/
    inspect_env.py               # CLI wrapper around env_inspect
    install_all.sh               # best-effort installer
    install_lib.sh               # helpers sourced by install_all
  vale/
    .vale.ini
    styles/Slop/                 # transparent custom rules
  tests/
    test_models.py
    test_normalize.py
    test_weights.py
    test_input_stats.py
    test_scoring_slop.py
    test_scoring_ai.py
    test_agreement.py
    test_runner_restart.py
    test_report.py
    fixtures/short.txt
  input/ raw/ normalized/ report/ logs/ envs/ tools/   # runtime dirs (tools/ may hold vendored bins)
```

---

### Task 1: Core models and adapter result contract

**Files:**
- Create: `text_audit/__init__.py`
- Create: `text_audit/models.py`
- Create: `tests/test_models.py`
- Create: `pyproject.toml`

**Interfaces:**
- Produces: `ToolStatus` enum (`OK`, `NOT_RUN`, `ERROR`); `ToolResult(tool, status, version, category, commands, raw_dir, native, normalized_score, findings_count, errors, warnings, info, reason, notes)`; `CATEGORY_SLOP | CATEGORY_PROSE | CATEGORY_STATS | CATEGORY_AI`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_models.py
from text_audit.models import ToolResult, ToolStatus, CATEGORY_SLOP

def test_not_run_result_has_no_normalized_score():
    r = ToolResult(
        tool="dslop",
        status=ToolStatus.NOT_RUN,
        version=None,
        category=CATEGORY_SLOP,
        commands=["pip install dslop"],
        raw_dir="raw/dslop",
        native=None,
        normalized_score=None,
        findings_count=0,
        errors=0,
        warnings=0,
        info=0,
        reason="PackageNotFoundError: dslop",
        notes="",
    )
    assert r.status == ToolStatus.NOT_RUN
    assert r.normalized_score is None
    assert "dslop" in r.reason
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /workspace/text-audit && python -m pytest tests/test_models.py::test_not_run_result_has_no_normalized_score -v`
Expected: FAIL (module not found or ToolResult missing)

- [ ] **Step 3: Write minimal implementation**

```toml
# pyproject.toml
[project]
name = "text-audit"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = []

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

```python
# text_audit/__init__.py
"""Local multi-tool text audit harness."""

# text_audit/models.py
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any

CATEGORY_SLOP = "slop"
CATEGORY_PROSE = "prose"
CATEGORY_STATS = "stats"
CATEGORY_AI = "ai_authorship"

class ToolStatus(str, Enum):
    OK = "OK"
    NOT_RUN = "NOT_RUN"
    ERROR = "ERROR"

@dataclass
class ToolResult:
    tool: str
    status: ToolStatus
    version: str | None
    category: str
    commands: list[str]
    raw_dir: str
    native: Any
    normalized_score: float | None
    findings_count: int
    errors: int
    warnings: int
    info: int
    reason: str
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /workspace/text-audit && python -m pytest tests/test_models.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /workspace/text-audit
git add pyproject.toml text_audit/__init__.py text_audit/models.py tests/test_models.py
git commit -m "feat: add ToolResult contract and project metadata"
```

---

### Task 2: Normalization heuristic

**Files:**
- Create: `text_audit/normalize.py`
- Create: `tests/test_normalize.py`

**Interfaces:**
- Consumes: finding severity counts + word_count
- Produces: `weighted_findings(errors, warnings, info) -> float`; `density(weighted, word_count) -> float`; `normalized_score(density) -> float` using `100 * (1 - exp(-density / 10))`; `normalize_from_counts(errors, warnings, info, word_count) -> float`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_normalize.py
import math
from text_audit.normalize import weighted_findings, density, normalized_score, normalize_from_counts

def test_weighted_findings():
    assert weighted_findings(1, 2, 3) == 3*1 + 2*2 + 1*3

def test_normalized_score_zero_density():
    assert normalized_score(0.0) == 0.0

def test_normalize_from_counts_matches_formula():
    w = weighted_findings(0, 5, 0)
    d = density(w, 1000)
    expected = 100 * (1 - math.exp(-d / 10))
    assert abs(normalize_from_counts(0, 5, 0, 1000) - expected) < 1e-9
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_normalize.py -v`
Expected: FAIL import error

- [ ] **Step 3: Write minimal implementation**

```python
# text_audit/normalize.py
from __future__ import annotations
import math

def weighted_findings(errors: int, warnings: int, info: int) -> float:
    return 3 * errors + 2 * warnings + 1 * info

def density(weighted: float, word_count: int) -> float:
    if word_count <= 0:
        return 0.0
    return weighted / word_count * 1000.0

def normalized_score(dens: float) -> float:
    return 100.0 * (1.0 - math.exp(-dens / 10.0))

def normalize_from_counts(errors: int, warnings: int, info: int, word_count: int) -> float:
    return normalized_score(density(weighted_findings(errors, warnings, info), word_count))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_normalize.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add text_audit/normalize.py tests/test_normalize.py
git commit -m "feat: add severity-density normalization heuristic"
```

---

### Task 3: Weight renormalization for missing tools

**Files:**
- Create: `text_audit/weights.py`
- Create: `tests/test_weights.py`

**Interfaces:**
- Produces: `renormalize(weights: dict[str, float], available: set[str]) -> dict[str, float]` that drops missing keys and rescales remaining to sum 1.0; empty available → empty dict

- [ ] **Step 1: Write the failing test**

```python
# tests/test_weights.py
from text_audit.weights import renormalize

def test_renormalize_drops_missing_and_rescales():
    w = {"a": 0.25, "b": 0.25, "c": 0.50}
    out = renormalize(w, {"a", "c"})
    assert set(out) == {"a", "c"}
    assert abs(sum(out.values()) - 1.0) < 1e-9
    assert abs(out["a"] - 0.25/0.75) < 1e-9
    assert abs(out["c"] - 0.50/0.75) < 1e-9

def test_renormalize_empty():
    assert renormalize({"a": 1.0}, set()) == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_weights.py -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```python
# text_audit/weights.py
from __future__ import annotations

def renormalize(weights: dict[str, float], available: set[str]) -> dict[str, float]:
    kept = {k: v for k, v in weights.items() if k in available}
    total = sum(kept.values())
    if total <= 0:
        return {}
    return {k: v / total for k, v in kept.items()}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_weights.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add text_audit/weights.py tests/test_weights.py
git commit -m "feat: renormalize ensemble weights when tools missing"
```

---

### Task 4: Input statistics

**Files:**
- Create: `text_audit/input_stats.py`
- Create: `tests/test_input_stats.py`
- Create: `tests/fixtures/short.txt`

**Interfaces:**
- Produces: `InputStats` dataclass + `compute_input_stats(path: Path) -> InputStats` with sha256, bytes, characters, words, sentences, paragraphs, text

- [ ] **Step 1: Write fixture and failing test**

```text
# tests/fixtures/short.txt
Hello world. This is a test.

Second paragraph here.
```

```python
# tests/test_input_stats.py
from pathlib import Path
from text_audit.input_stats import compute_input_stats

FIX = Path(__file__).parent / "fixtures" / "short.txt"

def test_compute_input_stats_basic():
    s = compute_input_stats(FIX)
    assert s.words >= 8
    assert s.sentences >= 2
    assert s.paragraphs == 2
    assert len(s.sha256) == 64
    assert s.bytes > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_input_stats.py -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```python
# text_audit/input_stats.py
from __future__ import annotations
import hashlib
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")

@dataclass
class InputStats:
    path: str
    sha256: str
    bytes: int
    characters: int
    words: int
    sentences: int
    paragraphs: int
    text: str

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d

def compute_input_stats(path: Path) -> InputStats:
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    paragraphs = [p for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    words = re.findall(r"\b\w+\b", text)
    sentences = [s for s in SENTENCE_SPLIT.split(text.strip()) if s.strip()] if text.strip() else []
    return InputStats(
        path=str(path),
        sha256=hashlib.sha256(raw).hexdigest(),
        bytes=len(raw),
        characters=len(text),
        words=len(words),
        sentences=len(sentences),
        paragraphs=len(paragraphs) if paragraphs else (1 if text.strip() else 0),
        text=text,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_input_stats.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add text_audit/input_stats.py tests/test_input_stats.py tests/fixtures/short.txt
git commit -m "feat: compute input SHA and basic text statistics"
```

---

### Task 5: Logging helpers and environment inspection

**Files:**
- Create: `text_audit/logging_util.py`
- Create: `text_audit/env_inspect.py`
- Create: `scripts/inspect_env.py`
- Create: `tests/test_env_inspect.py`

**Interfaces:**
- Produces: `append_log(path, message)`; `inspect_environment() -> dict` with keys os, arch, cpu, ram_bytes, gpu, python, pip, uv, node, npm, rustc, cargo, java, go, docker, disk_free_bytes

- [ ] **Step 1: Write the failing test**

```python
# tests/test_env_inspect.py
from text_audit.env_inspect import inspect_environment

def test_inspect_environment_has_required_keys():
    env = inspect_environment()
    for key in ["os", "arch", "cpu", "ram_bytes", "python", "disk_free_bytes"]:
        assert key in env
    assert env["python"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_env_inspect.py -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

Implement `logging_util.append_log` (mkdir parents, append timestamped line). Implement `inspect_environment` via `platform`, `/proc/meminfo` or `os.sysconf`, `shutil.disk_usage`, `shutil.which` + version flags for python/pip/uv/node/npm/rustc/cargo/java/go/docker, and best-effort GPU detection (`nvidia-smi`, ROCm, or note "none detected"). CLI `scripts/inspect_env.py` writes JSON to `logs/environment.json` and prints path.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_env_inspect.py -v`
Expected: PASS

Also run: `python scripts/inspect_env.py` → creates `logs/environment.json`

- [ ] **Step 5: Commit**

```bash
git add text_audit/logging_util.py text_audit/env_inspect.py scripts/inspect_env.py tests/test_env_inspect.py logs/.gitkeep
git commit -m "feat: environment inspection and append-only logs"
```

---

### Task 6: Adapter base helper and registry stub

**Files:**
- Create: `text_audit/adapters/__init__.py`
- Create: `text_audit/adapters/base.py`
- Create: `tests/test_adapter_base.py`

**Interfaces:**
- Produces: `ROOT = Path(__file__).resolve().parents[2]`; `ensure_raw_dir(tool) -> Path`; `run_cmd(commands: list[str], timeout, cwd, env) -> CompletedProcess-like dict` that never raises (captures returncode/stdout/stderr); `write_raw(tool, name, content)`; `ALL_ADAPTERS: list[callable]` initially empty then filled by later tasks

- [ ] **Step 1: Write failing test for run_cmd success and failure capture**

```python
from text_audit.adapters.base import run_cmd

def test_run_cmd_captures_failure_without_raising():
    result = run_cmd(["bash", "-c", "echo nope >&2; exit 7"])
    assert result["returncode"] == 7
    assert "nope" in result["stderr"]
```

- [ ] **Step 2: Run test to verify it fails**

- [ ] **Step 3: Implement `base.py` and empty registry in `__init__.py` exporting `get_adapters()`

- [ ] **Step 4: Run tests PASS

- [ ] **Step 5: Commit** `feat: add adapter subprocess helpers and registry`

---

### Task 7: Slop Index and agreement scoring

**Files:**
- Create: `text_audit/scoring_slop.py`
- Create: `text_audit/agreement.py`
- Create: `tests/test_scoring_slop.py`
- Create: `tests/test_agreement.py`

**Interfaces:**
- Produces: `SLOP_WEIGHTS` dict matching design (slopscore 0.25, dslop 0.20, slopsift 0.20, ai_slop_detect 0.10, slop_lint 0.05, vale 0.10, prose 0.10); `compute_slop_index(results: list[ToolResult]) -> dict` with score, band, weights_used, components; `band_for(score)`; `independent_agreement(phenomena: dict[str, list[str]]) -> list[dict]`

Prose tools (`proselint`, `write_good`, `harper`, `languagetool`) combine into single `prose` component as mean of available normalized scores before applying the 10% weight.

- [ ] **Step 1: Failing tests for renormalized index and bands**

```python
from text_audit.models import ToolResult, ToolStatus, CATEGORY_SLOP
from text_audit.scoring_slop import compute_slop_index, band_for

def _ok(tool, score):
    return ToolResult(tool, ToolStatus.OK, "1", CATEGORY_SLOP, [], f"raw/{tool}", {"score": score}, score, 0,0,0,0, "", "")

def test_slop_index_ignores_not_run():
    results = [_ok("slopscore", 40), ToolResult("dslop", ToolStatus.NOT_RUN, None, CATEGORY_SLOP, [], "raw/dslop", None, None, 0,0,0,0, "missing", "")]
    out = compute_slop_index(results)
    assert "dslop" not in out["weights_used"]
    assert out["score"] is not None

def test_band_for():
    assert band_for(10) == "LOW"
    assert band_for(40) == "MODERATE"
    assert band_for(60) == "HIGH"
    assert band_for(80) == "VERY HIGH"
```

Bands: `<25 LOW`, `<50 MODERATE`, `<75 HIGH`, else `VERY HIGH`.

- [ ] **Step 2–5:** implement, test, commit `feat: Slop Index and independent agreement helpers`

---

### Task 8: AI-Likeness ensemble (family-aware)

**Files:**
- Create: `text_audit/scoring_ai.py`
- Create: `tests/test_scoring_ai.py`

**Interfaces:**
- Produces: `FAMILY_WEIGHTS = {"deberta": 0.40, "binoculars": 0.35, "fastdetect": 0.25}`; map tools → families (`ai_detect`→deberta, `clarity`+`binoculars`→binoculars family mean, `fastdetectgpt`→fastdetect); `compute_ai_likeness(results) -> dict` with ensemble, agreement (LOW/MEDIUM/HIGH by spread), per_tool, families_used

- [ ] **Step 1: Failing test that Clarity + Binoculars do not double-weight**

```python
def test_binoculars_family_not_double_counted():
    # two OK results in binoculars family with scores 20 and 80 → family value 50, weight 0.35 after renormalize if only that family
    ...
```

- [ ] **Step 2–5:** implement using documented directional 0–100 conversion hooks per tool (`to_ai_likeness_score(tool, native)`) defaulting to passthrough only when adapter already stored `normalized_score` on AI category results; commit `feat: family-aware AI-Likeness ensemble`

---

### Task 9: Report writer

**Files:**
- Create: `text_audit/report.py`
- Create: `tests/test_report.py`

**Interfaces:**
- Produces: `write_reports(out_dir, environment, input_stats, tool_results, slop, ai, stats_native, corroborated, false_positives) -> dict paths` writing `report.md` and `report.json` with sections from the design (Executive, Environment, Input, Tool matrix, Slop/style, Statistical, AI-authorship, Corroborated, False positives, Final assessment placeholders for human section)

Human editorial section during smoke/setup: state `deferred until real user text`.

- [ ] **Step 1:** test that markdown contains `Slop Index:` and JSON has `slop_index` key
- [ ] **Step 2–5:** implement templates; commit `feat: write report.md and report.json`

---

### Task 10: Runner orchestration + restartability

**Files:**
- Create: `text_audit/runner.py`
- Create: `run_audit.py`
- Create: `tests/test_runner_restart.py`

**Interfaces:**
- Produces: `run_audit(input_path, force=False) -> dict` coordinating env (optional), stats, adapters from `get_adapters()`, skip if `raw/<tool>/meta.json` matches sha+version and status OK unless force; writes `normalized/results.json`; calls scoring + report

- [ ] **Step 1:** failing test with fake adapter list monkeypatch proving second run skips OK tool
- [ ] **Step 2–5:** implement; CLI `python run_audit.py [--force] [path]`; commit `feat: audit runner with restartable tool cache`

---

### Task 11: Best-effort installer

**Files:**
- Create: `scripts/install_lib.sh`
- Create: `scripts/install_all.sh`
- Create: `logs/.gitkeep`

**Interfaces:**
- `install_all.sh` creates venvs with `uv venv` when possible else `python -m venv`; attempts packages for slop/prose/stats; separately attempts ML envs; each step `|| log_fail`; writes `logs/install_status.json` lines via python helper or jq; never exits non-zero for individual failures (final exit 0 if script itself completed)

Install targets (record exact commands in log):
- `envs/slop`: slopscore-lint, dslop, git+ai-slop-detect, textstat, proselint
- Node: local `tools/node_modules` via npm init + slopsift, slop-lint, write-good OR npx at runtime
- Vale binary into `tools/vale` if downloadable for linux amd64
- LanguageTool: attempt; on failure mark NOT_RUN reason
- ML envs one-by-one with disk/RAM guard (skip if `MemAvailable < 3GiB` or `disk_free < 5GiB` before model pulls)

- [ ] **Step 1:** manually run `bash -n scripts/install_all.sh` (syntax)
- [ ] **Step 2:** implement scripts with `set +e` per install block
- [ ] **Step 3:** run `bash scripts/install_all.sh 2>&1 | tee logs/install.log` (long; OK if some fail)
- [ ] **Step 4:** verify `logs/install_status.json` or install.log lists each tool attempted
- [ ] **Step 5:** commit `feat: best-effort install_all for audit toolchains`

---

### Task 12: Deterministic slop adapters (A–E)

**Files:**
- Create: `text_audit/adapters/slopscore.py`
- Create: `text_audit/adapters/dslop_adapter.py`
- Create: `text_audit/adapters/slopsift.py`
- Create: `text_audit/adapters/ai_slop_detect.py`
- Create: `text_audit/adapters/slop_lint.py`
- Modify: `text_audit/adapters/__init__.py` to register them

**Interfaces:**
- Each exports `run(input_path: Path, word_count: int) -> ToolResult`
- On missing binary/module: `NOT_RUN` with reason
- On success: parse native output into errors/warnings/info; set `normalized_score` via native 0–100 if present else `normalize_from_counts`
- Write stdout/stderr/json under `raw/<tool>/`

- [ ] **Step 1:** for each adapter, unit-test the parser with fixture stdout strings (no need for real CLI in unit tests)
- [ ] **Step 2:** implement parsers + CLI invocation via `envs/slop` python or npx
- [ ] **Step 3:** integration: if tool installed, run on `tests/fixtures/short.txt`; else assert NOT_RUN
- [ ] **Step 4:** register in `get_adapters()`
- [ ] **Step 5:** commit `feat: add slop tool adapters A–E`

---

### Task 13: Vale + custom Slop rules + prose adapters (F–J) + stats

**Files:**
- Create: `vale/.vale.ini`
- Create: `vale/styles/Slop/*.yml` for phrases from design (ItIsImportantToNote, Delve, TestamentTo, InTodaysWorld, NotMerelyBut, MoreoverFurthermore, etc.) — generic only
- Create: adapters `vale_adapter.py`, `proselint_adapter.py`, `write_good.py`, `harper_adapter.py`, `languagetool_adapter.py`, `stats_adapter.py`
- Modify: registry

Stats adapter must compute textstat metrics + sentence length mean/median/stdev/cv/min/max, TTR, top bigrams/trigrams; store native dict; category STATS; no contribution to Slop Index directly (stats section only) except densities consumed by report.

- [ ] **Step 1–5:** TDD parsers where feasible; install Vale packages StylesPath; commit `feat: vale/custom slop styles, prose adapters, stats`

---

### Task 14: ML authorship adapters (K–N) best-effort

**Files:**
- Create: `text_audit/adapters/ai_detect.py`, `clarity_adapter.py`, `binoculars_adapter.py`, `fastdetectgpt_adapter.py`
- Modify: registry

Each adapter:
1. Check venv exists and import works
2. Check rough memory budget; if insufficient → `NOT_RUN` reason
3. Run documented local inference path
4. Map native score to 0–100 AI-likeness with notes citing threshold semantics
5. Never call remote APIs

- [ ] **Step 1–5:** implement; commit `feat: best-effort local AI authorship adapters`

---

### Task 15: Smoke run, READY matrix, README, handoff cleanup

**Files:**
- Create: `README.md`
- Create: `scripts/smoke.sh`
- Create: `logs/tool_matrix.md` (generated)
- Modify: clear `input/target.txt` after smoke or write `input/README.md` stating paste replaces this file

**Steps:**

- [ ] **Step 1:** Write `input/target.txt` containing exactly:

```text
SMOKE_PLACEHOLDER: The quick brown fox jumps over the lazy dog. This second sentence exists only to exercise the audit pipeline.
```

- [ ] **Step 2:** Run `python run_audit.py --force`

- [ ] **Step 3:** Generate `logs/tool_matrix.md` listing each planned tool with READY/NOT_RUN and reason

- [ ] **Step 4:** Truncate `input/target.txt` to empty or single comment line `# paste target text here` and document in README

- [ ] **Step 5:** README documents: layout, `bash scripts/install_all.sh`, `python run_audit.py`, epistemic rules, paste-in-chat operator flow

- [ ] **Step 6:** Commit `chore: smoke verification, tool matrix, README handoff`

- [ ] **Step 7:** Notify user setup is ready for a real sentence (operator message; not part of repo)

---

## Self-review (plan vs spec)

| Spec requirement | Task |
|---|---|
| Directory layout | pre-created + Tasks 5, 10, 15 |
| Env inspect | Task 5 |
| Input SHA/stats | Task 4 |
| Tools A–E | Tasks 11–12 |
| Vale/custom/prose F–J | Tasks 11, 13 |
| textstat/stats | Task 13 |
| ML K–N best-effort | Tasks 11, 14 |
| Isolation / pip freeze | Task 11 |
| Normalization formula | Task 2 |
| Slop Index + renormalize | Tasks 3, 7 |
| Independent agreement | Task 7 |
| AI ensemble family weights | Task 8 |
| Reports md/json | Task 9 |
| Restartable raw cache | Task 10 |
| No fabricated scores / NOT_RUN | Tasks 1, 12–14 |
| Epistemic constraint in report | Task 9 |
| Smoke + handoff | Task 15 |
| GitHub out of scope | honored (no task) |

Placeholder scan: none intentionally left.
Type consistency: `ToolResult` / `ToolStatus` / `normalize_from_counts` / `renormalize` / `compute_slop_index` / `compute_ai_likeness` / `run_audit` used uniformly.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-09-13-text-audit-harness.md`.

Two execution options:

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks, fast iteration
2. **Inline Execution** — execute tasks in this session with executing-plans, batch checkpoints

Which approach?
