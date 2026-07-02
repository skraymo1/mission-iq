"""Orchestrator — the Foundry-hosted brain that reasons across planes and acts.

Builds a single agent on the gpt-5.4 deployment, hands it the active skin's data
planes and action tools, and gives it operating instructions assembled from the
skin's five slots. One question in, one synthesized + action-ready answer out.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

from azure.identity import DefaultAzureCredential
from agent_framework.openai import OpenAIChatClient

from .actions import make_action_tools
from .config import Settings, settings_for_skin
from .live import (
    build_foundry_client,
    build_live_agent,
)
from .magentic import run_magentic
from .planes import RunContext, build_plane_tools
from .skins.schema import Skin


def build_client(settings: Settings) -> OpenAIChatClient:
    """Create the chat client against the Foundry gpt-5.4 deployment (AAD auth)."""
    return OpenAIChatClient(
        model=settings.model,
        azure_endpoint=settings.endpoint,
        api_version=settings.api_version,
        credential=DefaultAzureCredential(),
    )


def build_instructions(skin: Skin) -> str:
    return f"""You are Mission IQ, a mission-control assistant for a non-profit running the
"{skin.name}" mission.

This mission's frame (the five slots you optimize within):
- DEMAND: {skin.demand.strip()}
- SUPPLY: {skin.supply.strip()}
- GUARDRAILS: {skin.guardrails.strip()}
- IMPACT: {skin.impact.strip()}
- FEEDBACK: {skin.feedback.strip()}

You have four data planes, each a tool:
- Fabric records — the structured system of record (who/what is available, current needs).
- Web — live external conditions (closures, weather, public info).
- Docs — internal SOPs, policies, eligibility rules, tone guides.
- Work IQ — recent emails, Teams, and calendar context from the team.

And action tools: draft_outreach, create_task, trigger_workflow.

How to operate:
1. Pull from EVERY plane that's relevant — your value is synthesizing across
   sources, not answering from one. For a dispatch/matching question, that
   usually means Fabric (who's available + needs) AND Web (can they get there)
   AND Docs (do guardrails allow it).
2. Apply the guardrails. Never recommend someone ineligible, uncleared, or routed
   through a closed/hazardous path. Call out conflicts explicitly.
3. Rank your recommendation by impact, and say why each pick made the cut.
4. Turn the answer into progress: when the user needs to reach people or set a
   next step, call the action tools to stage outreach/tasks/workflows.
5. Be concise and decision-ready. Lead with the answer. Use short lists. Note any
   important caveat or assumption. Do not invent records that the tools didn't return.
"""


def build_agent(skin: Skin, ctx: RunContext, settings: Settings, client: OpenAIChatClient):
    tools = build_plane_tools(skin, ctx) + make_action_tools(skin, ctx)
    return client.as_agent(
        name="MissionIQ",
        instructions=build_instructions(skin),
        tools=tools,
    )


async def ask(agent, question: str) -> str:
    result = await agent.run(question)
    return result.text


@dataclass
class Clients:
    """Lazily-built chat clients shared across turns.

    Seeded skins use the OpenAIChatClient (Chat Completions over the deployment);
    live skins use the FoundryChatClient (Responses API + hosted connectors). We
    build each only on first use so an offline/seeded-only run never needs the
    Foundry project endpoint, and vice-versa.
    """

    settings: Settings
    _openai: Optional[OpenAIChatClient] = field(default=None, repr=False)
    _foundry: object = field(default=None, repr=False)

    @property
    def openai(self) -> OpenAIChatClient:
        if self._openai is None:
            self._openai = build_client(self.settings)
        return self._openai

    @property
    def foundry(self):
        if self._foundry is None:
            self._foundry = build_foundry_client(self.settings)
        return self._foundry


async def run_turn(skin: Skin, ctx: RunContext, settings: Settings, clients: Clients, question: str) -> str:
    """Answer one question with the right engine for the skin.

    Live skins reason over real Foundry connectors. By default they run the
    **Magentic** multi-agent engine (a manager on gpt-5.4 orchestrating the four
    persisted specialists), which populates `ctx.magentic` (plan/ledger/turns),
    `ctx.sources`, and `ctx.actions`. Set `MISSIONIQ_ENGINE=single` to fall back to
    the original single live agent. Seeded skins always reason over local planes that
    record their own touches. Either way, action tools stage proposals into ctx.
    """
    if skin.live:
        engine = os.getenv("MISSIONIQ_ENGINE", "magentic").strip().lower()
        if engine == "magentic":
            return await run_magentic(skin, ctx, settings, question)
        eff = settings_for_skin(settings, skin.id)
        agent = build_live_agent(skin, ctx, eff, clients.foundry)
        result = await agent.run(question)
        return result.text

    agent = build_agent(skin, ctx, settings, clients.openai)
    result = await agent.run(question)
    return result.text
