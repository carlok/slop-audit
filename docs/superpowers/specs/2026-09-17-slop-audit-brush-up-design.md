# slop-audit brush-up — design

Date: 2026-09-17  
Status: approved (2026-09-17); MIT author line: Carlo Perassi / 2026; Phase 1 next

## Goal

Polish private repo `carlok/slop-audit` so it reads as a finished, cloneable product on main, then clean internal naming and close the known independent-agreement gap — without adding heavy BERT-class detectors yet.

## Non-goals

- Hosted / cloud detection APIs
- Automatic rewriting of user prose
- Claiming authorship (“written by AI”)
- Shipping user sample/target text (keep `input/target.txt` and `report/` gitignored)
- Running or proving heavy detectors on SlopPer’s VM
- Merging heavy-detector work into main in this brush-up

## Phasing

### Phase 1 — Docs & packaging (first)

Deliver via a cloud-agent branch and PR into `master` / default branch:

1. **LICENSE** — MIT (approved default)
2. **README polish**
   - Clone URL: `https://github.com/carlok/slop-audit`
   - Clear install → run → outputs story
   - Explicit note that the import package remains `text_audit` until Phase 2
   - Remove leftover “GitHub later / setup out of scope” / local-only path framing that contradicts the live private repo
3. **pyproject.toml metadata** — description, authors/urls as appropriate, `readme = "README.md"` if supported by the layout
4. **CHANGELOG.md** — `0.1.0` = harness as currently shipped on GitHub
5. **Light docs cleanup** — tracked design/plan notes that still say GitHub publication is out of scope get a short “superseded: repo is `carlok/slop-audit` (private)” note or equivalent; do not rewrite history of the original design

**Success criteria (Phase 1):**

- Stranger cloning the private repo can follow README to install and run
- LICENSE + CHANGELOG present
- No sample prose committed
- Existing tests still green
- No package rename in this PR

### Phase 2 — Code hygiene (after Phase 1 merges)

1. Rename import package **`text_audit` → `slop_audit`** (package dir, imports, tests, `run_audit.py`, docs references)
2. Wire live **independent-agreement / corroborated findings** into the report (close the known gap: helper exists but live runs do not yet feed shared finding labels)
3. Drop stale worktree / path wording in matrix or install docs that still assume `.worktrees/feat-text-audit-harness`

**Success criteria (Phase 2):**

- `import slop_audit` works; no remaining `text_audit` import paths in code/tests (docs history may mention the old name once)
- Report shows corroborated / independent-agreement content when tools share labels; empty only when nothing corroborates
- Tests green including any new agreement tests

### Later (out of this brush-up) — Heavy detectors branch

Separate branch (name TBD, e.g. `feat/heavy-detectors`):

- Add adapters / install hooks for larger local models (BERT-class and similar) that do not fit SlopPer’s VM RAM budget
- Document that they are **not proven on the VM**; expected status there is `NOT_RUN` with a memory/deps reason
- User tries them on a machine with enough RAM after pull from GitHub
- Keep main’s best-effort behavior unchanged

## Constraints

- Prefer cloud agent for implementation PRs against `https://github.com/carlok/slop-audit`
- Epistemic rules unchanged (separate Slop Index vs AI-Likeness; no invented scores; never claim “written by AI”)
- One tool failure still must not abort a run

## Open questions (none blocking Phase 1)

- ~~Exact license author line~~ → **Carlo Perassi / 2026** (approved)
- Heavy-detector branch contents and model list — deferred until after Phase 2
