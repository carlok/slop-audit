"""Adapter registry for text-audit tools."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from . import (
    ai_slop_detect,
    dslop_adapter,
    harper_adapter,
    languagetool_adapter,
    proselint_adapter,
    slop_lint,
    slopscore,
    slopsift,
    stats_adapter,
    vale_adapter,
    write_good,
)

ALL_ADAPTERS: list[Callable[..., Any]] = [
    slopscore.run,
    dslop_adapter.run,
    slopsift.run,
    ai_slop_detect.run,
    slop_lint.run,
    vale_adapter.run,
    proselint_adapter.run,
    write_good.run,
    harper_adapter.run,
    languagetool_adapter.run,
    stats_adapter.run,
]


def get_adapters() -> list[Callable[..., Any]]:
    """Return registered adapter callables."""
    return list(ALL_ADAPTERS)
