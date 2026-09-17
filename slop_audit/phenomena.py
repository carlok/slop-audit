"""Map style/slop/prose tool findings to shared labels for independent agreement."""

from __future__ import annotations

import re

from slop_audit.agreement import independent_agreement
from slop_audit.slop_edits import collect_style_finding_items

_WHITESPACE = re.compile(r"\s+")


def phenomenon_key(item: dict[str, str]) -> str:
    """Best-effort label: quoted span when present, else normalized rule id."""
    quote = (item.get("quote") or "").strip().lower()
    if quote:
        quote = _WHITESPACE.sub(" ", quote)
        if len(quote) > 100:
            quote = quote[:100]
        return f"span:{quote}"
    rule = (item.get("rule") or "unknown").strip().lower()
    return f"rule:{rule}"


def display_phenomenon(key: str) -> str:
    if key.startswith("span:"):
        return key[5:]
    if key.startswith("rule:"):
        return key[5:]
    return key


def build_phenomena_map(tool_results: list) -> dict[str, list[str]]:
    """Tool name lists per phenomenon key (style/slop/prose only; see slop_edits)."""
    phenomena: dict[str, list[str]] = {}
    for item in collect_style_finding_items(tool_results):
        tool = str(item.get("tool") or "")
        if not tool:
            continue
        key = phenomenon_key(item)
        phenomena.setdefault(key, []).append(tool)
    return phenomena


def corroborated_findings(tool_results: list) -> list[dict]:
    """Rows for the report when two or more tools share a phenomenon label."""
    rows = independent_agreement(build_phenomena_map(tool_results))
    out: list[dict] = []
    for row in rows:
        if row["count"] < 2:
            continue
        out.append(
            {
                "phenomenon": display_phenomenon(row["phenomenon"]),
                "tools": row["tools"],
                "count": row["count"],
            }
        )
    return out
