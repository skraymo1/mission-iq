"""Web plane — live external conditions (road closures, weather, public info).

Deterministic by default (serves a seeded snapshot) so demos never depend on the
network. Set MISSIONIQ_LIVE_WEB=1 to attempt a real fetch; on any failure it
falls back to the snapshot. Go-live swap: the Foundry native web/Bing-grounding
tool or your search provider of choice.
"""
from __future__ import annotations

import json
from typing import Annotated, Callable

from pydantic import Field

from ..config import LIVE_WEB
from ..skins.schema import Skin
from .base import RunContext, load_data


def _try_live(query: str) -> str | None:
    if not LIVE_WEB:
        return None
    try:  # pragma: no cover - network optional
        import httpx

        resp = httpx.get(
            "https://duckduckgo.com/html/",
            params={"q": query},
            timeout=4.0,
            headers={"User-Agent": "MissionIQ/0.1"},
        )
        if resp.status_code == 200 and resp.text:
            return f"(live web results retrieved for '{query}' — parse client-side)"
    except Exception:
        return None
    return None


def make_web_tool(skin: Skin, ctx: RunContext) -> Callable[..., str]:
    snapshot = load_data(skin.id, "web")

    def web_lookup(
        query: Annotated[
            str,
            Field(description="What to check on the live web, e.g. 'road closures near Houston tonight'."),
        ],
    ) -> str:
        ctx.touch("Web", "🌐", query)
        live = _try_live(query)
        if live:
            return live
        return json.dumps(snapshot, indent=2)

    web_lookup.__doc__ = (
        "Look up current, real-world external conditions on the web (road and "
        "weather closures, public advisories, local news). Use this whenever the "
        "answer depends on what is happening right now in the outside world."
    )
    return web_lookup


def make_situation_tool(skin: Skin) -> Callable[..., str]:
    """A client-side 'field situation report' tool for the hybrid Web specialist.

    The Field Response Web specialist runs client-side over this curated crisis
    snapshot (skin web.json) instead of live Bing, so the scripted outbreak /
    border-closure / advisory override lands deterministically on stage. Source
    attribution is recorded by the Magentic orchestrator at the agent grain, so
    this tool does not touch the RunContext itself (avoids double-counting).
    """
    snapshot = load_data(skin.id, "web")

    def field_situation_report(
        zone: Annotated[
            str,
            Field(description="Crisis zone or country to check, e.g. 'Chad' or 'Am Timan'."),
        ] = "",
    ) -> str:
        return json.dumps(snapshot, indent=2)

    field_situation_report.__doc__ = (
        "Get the current field situation report for the crisis zones in play — "
        "outbreak declarations, security advisories, border/crossing and no-fly "
        "status, open air/road corridors, and regional weather. ALWAYS call this "
        "before judging whether a candidate can actually reach the zone."
    )
    return field_situation_report
