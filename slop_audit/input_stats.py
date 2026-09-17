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
