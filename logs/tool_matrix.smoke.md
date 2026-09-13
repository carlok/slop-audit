# Tool READY / NOT_RUN matrix (smoke)

Generated: 2026-09-13T14:53:28Z (smoke.sh)
Input SHA-256: 9629185d9de3df5f8433cfff842ae2a728e56448324a6462b9063afc8590c857

Authoritative handoff matrix (install + notes): `logs/tool_matrix.md`.
This file is the thin smoke refresh only.

| ID | Tool | Matrix | Run status | Reason |
|----|------|--------|------------|--------|
| A | `slopscore` | READY | OK | OK |
| B | `dslop` | READY | OK | OK |
| C | `slopsift` | READY | OK | OK |
| D | `ai_slop_detect` | READY | OK | OK |
| E | `slop_lint` | READY | OK | OK |
| F | `vale` | READY | OK | OK |
| G | `proselint` | READY | OK | OK |
| H | `write_good` | READY | OK | OK |
| I | `harper` | READY | OK | Harper via Vale Harper style package (no direct harper CLI) |
| J | `languagetool` | READY | OK | local LanguageTool only (no cloud API) |
| stats | `stats` | READY | OK | descriptive stats only; not used in Slop Index |
| K | `ai_detect` | READY | OK | AI-likeness = model_ai_pct (mean sentence P(AI)×100). Thresholds: >50 LIKELY AI, <40 LIKELY HUMAN, else MIXED (ai_detect.detector.verdict). Sentence label AI if ai_prob>=0.5. Local weights only; never hosted detection APIs. model=desklib. |
| L | `clarity` | READY | OK | Clarity Binoculars-style score: lower = more AI-like. Labels: score < threshold_low → ai; score > threshold_high → human; else uncertain (defaults binoculars low=0.905 high=1.11; fast mode uses FAST_THRESHOLD_*). AI-likeness mapped linearly so score=low → 100, score=high → 0 (clamp 0–100). Local HF causal LMs only; never hosted detection APIs. mode=binoculars. |
| M | `binoculars` | NOT_RUN | NOT_RUN | insufficient memory for Binoculars Falcon-7B×2: MemAvailable=14342844416 < need=21474836480 (20.0 GiB) |
| N | `fastdetectgpt` | NOT_RUN | NOT_RUN | insufficient memory for Fast-DetectGPT gpt-j-6B + gpt-neo-2.7B: MemAvailable=14259302400 < need=15032385536 (14.0 GiB) |

**Counts:** READY=13, NOT_RUN=2, total=15

