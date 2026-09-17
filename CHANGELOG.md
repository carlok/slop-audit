# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-09-17

### Added

- Local multi-tool harness for prose audit: AI-slop / formulaic style, general writing issues, descriptive stats, and (separately) local AI-authorship detector signals.
- **Slop Index** (0–100 + band) from linters and slop tools, kept separate from **AI-Likeness Ensemble**.
- Deterministic edit suggestions sourced from tools (quote, rule, tool message) — no LLM rewrite prose.
- Per-tool matrix with `OK` / `NOT_RUN` / `ERROR` and exact reasons; one tool failure does not abort a run.
- Install scripts, smoke check, Vale custom styles, cache keyed by input SHA + tool version.
- Initial publication on private GitHub: [carlok/slop-audit](https://github.com/carlok/slop-audit).

### Notes

- Python import package remains `text_audit` until a future rename (Phase 2).
- Heavy local ML detectors may report `NOT_RUN` when RAM is below their budgets; expected on constrained hosts.
