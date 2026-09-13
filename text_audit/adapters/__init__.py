"""Adapter registry for text-audit tools."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

ALL_ADAPTERS: list[Callable[..., Any]] = []


def get_adapters() -> list[Callable[..., Any]]:
    """Return registered adapter callables (initially empty)."""
    return list(ALL_ADAPTERS)
