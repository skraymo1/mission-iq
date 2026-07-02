"""Work plane — the day-to-day workplace (email, Teams, calendar) via Work IQ / M365.

Seeded snapshot today; go-live swap is Work IQ / Microsoft Graph against real
M365 data.
"""
from __future__ import annotations

import json
from typing import Annotated, Callable

from pydantic import Field

from ..skins.schema import Skin
from .base import RunContext, load_data


def make_work_tool(skin: Skin, ctx: RunContext) -> Callable[..., str]:
    data = load_data(skin.id, "work")
    items = data.get("items", [])

    def search_workplace(
        query: Annotated[
            str,
            Field(description="What to look for across recent emails, Teams messages, and calendar items."),
        ],
    ) -> str:
        ctx.touch("Work IQ", "💼", query)
        return json.dumps(items, indent=2)

    search_workplace.__doc__ = (
        "Search the team's recent workplace activity — emails, Teams messages, and "
        "calendar — to pull in context like what a coordinator just asked for or "
        "what was decided in a meeting. Use this for 'what did the team say/decide' "
        "context that isn't in the structured records."
    )
    return search_workplace
