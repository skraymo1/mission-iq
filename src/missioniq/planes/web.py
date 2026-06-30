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
