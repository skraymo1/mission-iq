"""Docs plane — internal knowledge (SOPs, policies, guides) via Foundry IQ.

Seeded snapshot today; go-live swap is the Foundry native file-search / RAG tool
over your document store.
"""
from __future__ import annotations

import json
from typing import Annotated, Callable

from pydantic import Field

from ..skins.schema import Skin
from .base import RunContext, load_data


def make_docs_tool(skin: Skin, ctx: RunContext) -> Callable[..., str]:
    data = load_data(skin.id, "docs")
    documents = data.get("documents", [])

    def search_docs(
        query: Annotated[
            str,
            Field(description="What policy, SOP, or guidance to look up in internal docs."),
        ],
    ) -> str:
        ctx.touch("Docs", "📄", query)
        q = query.lower()
        hits = [d for d in documents if any(t in (d["title"] + d["snippet"]).lower() for t in q.split() if len(t) > 2)]
        return json.dumps(hits or documents, indent=2)

    search_docs.__doc__ = (
        "Search internal documents — standard operating procedures, policies, "
        "eligibility rules, and tone guides. Use this to make sure an answer "
        "follows the organization's own guardrails and guidance."
    )
    return search_docs
