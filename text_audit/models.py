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
