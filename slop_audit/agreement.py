from __future__ import annotations


def independent_agreement(phenomena: dict[str, list[str]]) -> list[dict]:
    """Count distinct tools flagging each phenomenon; highest agreement first."""
    rows: list[dict] = []
    for name, tools in phenomena.items():
        unique = sorted(set(tools))
        rows.append({
            "phenomenon": name,
            "tools": unique,
            "count": len(unique),
        })
    rows.sort(key=lambda row: (-row["count"], row["phenomenon"]))
    return rows
