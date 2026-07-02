"""Planes package — the pluggable data sources the orchestrator reasons across."""
from __future__ import annotations

from typing import Callable

from ..skins.schema import Skin
from .base import ProposedAction, RunContext, SourceTouch
from .docs import make_docs_tool
from .fabric import make_fabric_tool
from .web import make_web_tool
from .work import make_work_tool

__all__ = [
    "RunContext",
    "SourceTouch",
    "ProposedAction",
    "build_plane_tools",
]


def build_plane_tools(skin: Skin, ctx: RunContext) -> list[Callable[..., str]]:
    """Construct the four data-plane tools, each bound to the active skin + context."""
    return [
        make_fabric_tool(skin, ctx),
        make_web_tool(skin, ctx),
        make_docs_tool(skin, ctx),
        make_work_tool(skin, ctx),
    ]
