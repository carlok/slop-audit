"""Deterministic extraction of Slop-Index-relevant edit suggestions from tool natives.

No LLM paraphrasing: messages and rule ids come from the tools themselves.
"""

from __future__ import annotations

import re
from typing import Any

from text_audit.models import CATEGORY_AI, CATEGORY_STATS, ToolResult, ToolStatus

# Tools / categories that feed Slop Index (exclude AI authorship + stats).
_SKIP_CATEGORIES = {CATEGORY_AI, CATEGORY_STATS}

_WRITE_GOOD_LINE = re.compile(
    r'^(?P<path>.+):(?P<line>\d+):(?P<col>\d+):(?P<msg>.*)$'
)
_DSLOP_VIOLATION = re.compile(
    r'^(?P<path>.+):(?P<line>\d+):(?P<col>\d+)\s+(?P<rule>\S+)\s*$'
)
_DSLOP_FIX = re.compile(r'^\s{2}(?P<rule>[^:]+):\s*(?P<msg>.+)\s*$')


def _status_ok(r: ToolResult | dict) -> bool:
    status = r.status if isinstance(r, ToolResult) else r.get("status")
    if isinstance(status, ToolStatus):
        return status == ToolStatus.OK
    return status == "OK" or status == ToolStatus.OK.value


def _fields(r: ToolResult | dict) -> tuple[str, str, Any]:
    if isinstance(r, ToolResult):
        return r.tool, r.category, r.native
    return str(r.get("tool") or ""), str(r.get("category") or ""), r.get("native")


def _item(
    *,
    tool: str,
    rule: str,
    message: str,
    quote: str | None = None,
    location: str | None = None,
) -> dict[str, str]:
    out = {
        "tool": tool,
        "rule": rule,
        "message": message.strip(),
    }
    if quote:
        out["quote"] = quote
    if location:
        out["location"] = location
    return out


def _dedupe_key(item: dict[str, str]) -> tuple[str, str, str]:
    return (
        (item.get("quote") or "").lower(),
        (item.get("rule") or "").lower(),
        (item.get("message") or "").lower(),
    )


def _from_vale(tool: str, native: Any) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    if not isinstance(native, dict):
        return items
    alerts = native.get("alerts") or []
    # Some adapters nest file→alerts; flatten if needed
    if not alerts and isinstance(native, dict):
        for v in native.values():
            if isinstance(v, list) and v and isinstance(v[0], dict) and "Check" in v[0]:
                alerts = v
                break
    for a in alerts:
        if not isinstance(a, dict):
            continue
        rule = str(a.get("Check") or a.get("check") or "vale")
        message = str(a.get("Message") or a.get("message") or "")
        quote = a.get("Match") or a.get("match")
        line = a.get("Line") or a.get("line")
        loc = f"line {line}" if line is not None else None
        if message:
            items.append(
                _item(
                    tool=tool,
                    rule=rule,
                    message=message,
                    quote=str(quote) if quote else None,
                    location=loc,
                )
            )
    return items


def _from_write_good(tool: str, native: Any) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    findings = []
    if isinstance(native, dict):
        findings = native.get("findings") or []
        if not findings and native.get("stdout"):
            findings = str(native["stdout"]).splitlines()
    elif isinstance(native, list):
        findings = native
    for line in findings:
        s = str(line).strip()
        if not s:
            continue
        m = _WRITE_GOOD_LINE.match(s)
        if m:
            msg = m.group("msg").strip().strip('"')
            # quote often appears as "word" at start of msg
            quote = None
            qm = re.match(r'^"([^"]+)"\s*(.*)$', msg)
            if qm:
                quote, rest = qm.group(1), qm.group(2)
                message = rest or msg
            else:
                message = msg
            loc = f"line {m.group('line')}:{m.group('col')}"
            items.append(
                _item(
                    tool=tool,
                    rule="write-good",
                    message=message,
                    quote=quote,
                    location=loc,
                )
            )
        else:
            items.append(_item(tool=tool, rule="write-good", message=s))
    return items


def _from_proselint(tool: str, native: Any) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    if not isinstance(native, dict):
        return items
    result = native.get("result") or native
    if not isinstance(result, dict):
        return items
    for _path, payload in result.items():
        if not isinstance(payload, dict):
            continue
        for diag in payload.get("diagnostics") or []:
            if not isinstance(diag, dict):
                continue
            rule = str(diag.get("check_path") or "proselint")
            message = str(diag.get("message") or "")
            pos = diag.get("pos")
            loc = None
            if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                loc = f"line {pos[0]}:{pos[1]}"
            # proselint rarely returns the matched token; leave quote empty
            if message:
                items.append(
                    _item(tool=tool, rule=rule, message=message, location=loc)
                )
    return items


def _from_dslop(tool: str, native: Any) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    if not isinstance(native, dict):
        return items
    stdout = str(native.get("stdout") or "")
    fixes: dict[str, str] = {}
    # Pass 1: FIX: block messages
    in_fix = False
    for line in stdout.splitlines():
        if line.strip() == "fix:":
            in_fix = True
            continue
        if in_fix:
            fm = _DSLOP_FIX.match(line)
            if fm:
                fixes[fm.group("rule").strip()] = fm.group("msg").strip()
            elif line.strip() == "":
                continue
            else:
                in_fix = False
    # Pass 2: violation lines + kurtosis
    for line in stdout.splitlines():
        vm = _DSLOP_VIOLATION.match(line.strip())
        if vm:
            rule = vm.group("rule")
            loc = f"line {vm.group('line')}:{vm.group('col')}"
            msg = fixes.get(rule) or rule
            items.append(
                _item(tool=tool, rule=rule, message=msg, location=loc)
            )
        elif "sentence-length-kurtosis" in line and "FIX:" not in line:
            rule = "sentence-length-kurtosis"
            msg = fixes.get(rule) or line.strip()
            items.append(_item(tool=tool, rule=rule, message=msg))
    for v in native.get("violations") or []:
        s = str(v).strip()
        vm = _DSLOP_VIOLATION.match(s)
        if not vm:
            continue
        rule = vm.group("rule")
        loc = f"line {vm.group('line')}:{vm.group('col')}"
        if any(i.get("rule") == rule and i.get("location") == loc for i in items):
            continue
        items.append(
            _item(tool=tool, rule=rule, message=fixes.get(rule) or rule, location=loc)
        )
    return items


def _from_slopscore(tool: str, native: Any) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    if not isinstance(native, dict):
        return items
    for ev in native.get("evidence") or []:
        if not isinstance(ev, dict):
            continue
        rule = str(ev.get("dimension") or ev.get("id") or ev.get("rule") or "evidence")
        message = str(ev.get("message") or ev.get("explanation") or ev.get("text") or "")
        quote = ev.get("span") or ev.get("quote") or ev.get("match")
        if isinstance(quote, (list, dict)):
            quote = str(quote)
        if message:
            items.append(
                _item(
                    tool=tool,
                    rule=rule,
                    message=message,
                    quote=str(quote) if quote else None,
                )
            )
    return items


def _from_ai_slop_detect(tool: str, native: Any) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    if not isinstance(native, dict):
        return items
    for hit in native.get("hits") or []:
        if not isinstance(hit, dict):
            continue
        rule = str(hit.get("kind") or hit.get("rule") or "hit")
        message = str(hit.get("message") or hit.get("note") or rule)
        quote = hit.get("text") or hit.get("match") or hit.get("span")
        items.append(
            _item(
                tool=tool,
                rule=rule,
                message=message,
                quote=str(quote) if quote else None,
            )
        )
    return items


def _from_slopsift(tool: str, native: Any) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    rows = native if isinstance(native, list) else [native] if isinstance(native, dict) else []
    for row in rows:
        if not isinstance(row, dict):
            continue
        for msg in row.get("messages") or []:
            if not isinstance(msg, dict):
                continue
            rule = str(msg.get("ruleId") or msg.get("rule") or "slopsift")
            message = str(msg.get("message") or "")
            quote = None
            loc = None
            if msg.get("line") is not None:
                loc = f"line {msg.get('line')}"
                if msg.get("column") is not None:
                    loc += f":{msg.get('column')}"
            # some messages embed source
            if message:
                items.append(
                    _item(tool=tool, rule=rule, message=message, quote=quote, location=loc)
                )
    return items


def _from_slop_lint(tool: str, native: Any) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    if not isinstance(native, dict):
        return items
    stdout = str(native.get("stdout") or "")
    # Only surface non-clean lines that look like findings
    for line in stdout.splitlines():
        s = line.strip()
        if not s or s.endswith("clean ✓") or s.startswith("0 em-dash") or s.startswith("FAIL on"):
            continue
        if re.search(r"warning|em-dash|error", s, re.I) and "across" not in s:
            items.append(_item(tool=tool, rule="slop-lint", message=s))
    return items


_EXTRACTORS = {
    "vale": _from_vale,
    "write_good": _from_write_good,
    "proselint": _from_proselint,
    "dslop": _from_dslop,
    "slopscore": _from_slopscore,
    "ai_slop_detect": _from_ai_slop_detect,
    "slopsift": _from_slopsift,
    "slop_lint": _from_slop_lint,
    "harper": _from_vale,  # harper via Vale JSON alerts if present
}


def collect_slop_edit_suggestions(tool_results: list) -> list[dict[str, str]]:
    """Return deduped, tool-sourced edits that can lower the Slop Index."""
    collected: list[dict[str, str]] = []
    for r in tool_results or []:
        if not _status_ok(r):
            continue
        tool, category, native = _fields(r)
        if category in _SKIP_CATEGORIES:
            continue
        if tool == "stats":
            continue
        extractor = _EXTRACTORS.get(tool)
        if extractor is None:
            continue
        collected.extend(extractor(tool, native))

    seen: set[tuple[str, str, str]] = set()
    out: list[dict[str, str]] = []
    for item in collected:
        key = _dedupe_key(item)
        if key in seen:
            continue
        if not item.get("message"):
            continue
        seen.add(key)
        out.append(item)
    return out
