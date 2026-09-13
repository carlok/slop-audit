"""Write report.md and report.json for a text-audit run."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from text_audit.models import ToolResult


def _as_dict(obj: Any) -> Any:
    if obj is None:
        return None
    if hasattr(obj, "to_dict") and callable(obj.to_dict):
        return obj.to_dict()
    if isinstance(obj, dict):
        return obj
    return obj


def _tool_rows(tool_results: list) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for r in tool_results:
        if isinstance(r, ToolResult):
            d = r.to_dict()
        elif isinstance(r, dict):
            d = r
        else:
            d = _as_dict(r)
        rows.append(
            {
                "tool": d.get("tool"),
                "status": d.get("status"),
                "version": d.get("version"),
                "category": d.get("category"),
                "normalized_score": d.get("normalized_score"),
                "findings_count": d.get("findings_count"),
                "reason": d.get("reason") or "",
                "notes": d.get("notes") or "",
            }
        )
    return rows


def _fmt_score(val: Any) -> str:
    if val is None:
        return "n/a (no contributing tools)"
    if isinstance(val, float):
        return f"{val:.2f}"
    return str(val)


def _executive_summary(slop: dict, ai: dict, tool_rows: list[dict]) -> str:
    """Concentration + N-of-M form; never claim text was written by AI."""
    band = slop.get("band")
    score = slop.get("score")
    if band and score is not None:
        conc = f"{band.lower()} concentration of stylistic patterns associated with formulaic or LLM-generated prose (Slop Index: {_fmt_score(score)})"
    elif score is not None:
        conc = f"stylistic Slop Index of {_fmt_score(score)} (band unavailable)"
    else:
        conc = "insufficient style-tool data to estimate a Slop Index"

    ai_tools = [r for r in tool_rows if r.get("category") == "ai_authorship"]
    ok_ai = [
        r
        for r in ai_tools
        if r.get("status") == "OK" and r.get("normalized_score") is not None
    ]
    # Count detectors classifying as AI-like: score >= 50 heuristic for narrative only
    m = len(ok_ai)
    n = sum(1 for r in ok_ai if float(r["normalized_score"]) >= 50.0)
    ensemble = ai.get("ensemble")
    agreement = ai.get("agreement")
    if m == 0:
        authorship = "0 of 0 local authorship detectors ran successfully"
    else:
        authorship = (
            f"{n} of {m} local authorship detectors classify it as AI-like"
        )
        if ensemble is not None:
            authorship += f" (ensemble {_fmt_score(ensemble)}, agreement {agreement or 'n/a'})"

    return (
        f"The text has a {conc}, and {authorship}. "
        "Low detector scores do not establish human authorship. "
        "This report does not conclude that the text was written by a human or by an AI system."
    )


def _render_markdown(payload: dict[str, Any]) -> str:
    env = payload["environment"]
    inp = payload["input_stats"]
    slop = payload["slop_index"]
    ai = payload["ai_likeness"]
    stats = payload["statistical"]
    tools = payload["tool_matrix"]
    corr = payload["corroborated"]
    fps = payload["false_positives"]
    executive = payload["executive"]

    lines: list[str] = []
    lines.append("# Text Audit Report")
    lines.append("")
    lines.append("## Executive")
    lines.append("")
    lines.append(executive)
    lines.append("")
    lines.append("## Environment")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(env, indent=2, default=str))
    lines.append("```")
    lines.append("")
    lines.append("## Input")
    lines.append("")
    # Omit full text body from markdown summary if present — keep stats
    inp_view = {k: v for k, v in (inp or {}).items() if k != "text"}
    lines.append("```json")
    lines.append(json.dumps(inp_view, indent=2, default=str))
    lines.append("```")
    lines.append("")
    lines.append("## Tool matrix")
    lines.append("")
    lines.append("| Tool | Status | Category | Score | Reason |")
    lines.append("| --- | --- | --- | --- | --- |")
    for r in tools:
        score = r.get("normalized_score")
        score_s = "" if score is None else f"{score:.2f}" if isinstance(score, float) else str(score)
        reason = (r.get("reason") or "").replace("|", "\\|")
        lines.append(
            f"| {r.get('tool')} | {r.get('status')} | {r.get('category')} | {score_s} | {reason} |"
        )
    lines.append("")
    lines.append("## Slop / style")
    lines.append("")
    lines.append(f"Slop Index: {_fmt_score(slop.get('score'))}")
    lines.append("")
    lines.append(f"Band: {slop.get('band') or 'n/a'}")
    lines.append("")
    lines.append("Weights used (renormalized over available tools):")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(slop.get("weights_used") or {}, indent=2))
    lines.append("```")
    lines.append("")
    lines.append("Components:")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(slop.get("components") or {}, indent=2))
    lines.append("```")
    lines.append("")
    lines.append("## Statistical")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(stats or {}, indent=2, default=str))
    lines.append("```")
    lines.append("")
    lines.append("## AI-authorship")
    lines.append("")
    lines.append(
        "AI-Likeness Ensemble is separate from the Slop Index. "
        "Scores reflect detector outputs under documented conversion; "
        "they are not proof of authorship."
    )
    lines.append("")
    lines.append(f"Ensemble: {_fmt_score(ai.get('ensemble'))}")
    lines.append("")
    lines.append(f"Agreement: {ai.get('agreement') or 'n/a'}")
    lines.append("")
    lines.append("```json")
    lines.append(
        json.dumps(
            {
                "per_tool": ai.get("per_tool") or {},
                "families_used": ai.get("families_used") or {},
            },
            indent=2,
        )
    )
    lines.append("```")
    lines.append("")
    lines.append("## Corroborated")
    lines.append("")
    if not corr:
        lines.append("_No corroborated phenomena recorded._")
    else:
        lines.append("| Phenomenon | Count | Tools |")
        lines.append("| --- | --- | --- |")
        for row in corr:
            tools_s = ", ".join(row.get("tools") or [])
            lines.append(
                f"| {row.get('phenomenon')} | {row.get('count')} | {tools_s} |"
            )
    lines.append("")
    lines.append("## False positives")
    lines.append("")
    if not fps:
        lines.append("_None flagged._")
    else:
        for item in fps:
            if isinstance(item, dict):
                lines.append(f"- {json.dumps(item, default=str)}")
            else:
                lines.append(f"- {item}")
    lines.append("")
    lines.append("## Final assessment")
    lines.append("")
    lines.append(executive)
    lines.append("")
    lines.append("### Human editorial")
    lines.append("")
    lines.append("deferred until real user text")
    lines.append("")
    return "\n".join(lines)


def write_reports(
    out_dir,
    environment,
    input_stats,
    tool_results,
    slop,
    ai,
    stats_native,
    corroborated,
    false_positives,
) -> dict:
    """Write report.md and report.json; return paths dict with md/json keys."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    env_d = _as_dict(environment) or {}
    inp_d = _as_dict(input_stats) or {}
    slop_d = dict(slop or {})
    ai_d = dict(ai or {})
    stats_d = _as_dict(stats_native) or {}
    corr_l = list(corroborated or [])
    fp_l = list(false_positives or [])
    tool_rows = _tool_rows(list(tool_results or []))

    executive = _executive_summary(slop_d, ai_d, tool_rows)

    payload: dict[str, Any] = {
        "executive": executive,
        "environment": env_d,
        "input_stats": {k: v for k, v in inp_d.items() if k != "text"},
        "tool_matrix": tool_rows,
        "slop_index": slop_d,
        "statistical": stats_d,
        "ai_likeness": ai_d,
        "corroborated": corr_l,
        "false_positives": fp_l,
        "human_editorial": "deferred until real user text",
        "epistemic_note": (
            "Do not assert authorship; report stylistic concentration and "
            "N of M detector classifications only."
        ),
    }

    md_path = out / "report.md"
    json_path = out / "report.json"
    md_path.write_text(_render_markdown(payload), encoding="utf-8")
    json_path.write_text(
        json.dumps(payload, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    return {"md": str(md_path), "json": str(json_path)}
