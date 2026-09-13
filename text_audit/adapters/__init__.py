"""Adapter registry for text-audit tools."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from . import ai_slop_detect, dslop_adapter, slop_lint, slopscore, slopsift

ALL_ADAPTERS: list[Callable[..., Any]] = [
    slopscore.run,
    dslop_adapter.run,
    slopsift.run,
    ai_slop_detect.run,
    slop_lint.run,
]


def get_adapters() -> list[Callable[..., Any]]:
    """Return registered adapter callables."""
    return list(ALL_ADAPTERS)
