r"""Provision the Mission IQ specialist team as **persisted Foundry PromptAgents**.

Re-runnable / idempotent: for each specialist we look at the latest persisted
version and only publish a new version when the instructions or tool wiring
changed. Run it after editing `agents_spec.py` to push the team to Foundry.

    $env:PYTHONIOENCODING="utf-8"; $env:PYTHONUTF8="1"; $env:PYTHONPATH="src"
    .\.venv\Scripts\python.exe scripts\provision_foundry_agents.py

The agents then appear in the Foundry portal (Agents list) and become the
participants the in-app Magentic orchestration drives at runtime.
"""
from __future__ import annotations

import asyncio
import os
import sys

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition
from agent_framework.foundry import FoundryChatClient, to_prompt_agent

from missioniq.config import load_settings, settings_for_skin
from missioniq.live import build_credential
from missioniq.agents_spec import TEAMS, AgentSpec


def _build_definition(spec: AgentSpec, settings) -> PromptAgentDefinition:
    """Convert a specialist spec into a Foundry PromptAgentDefinition.

    We build a throwaway Agent-Framework agent bound to a FoundryChatClient
    (which carries the model deployment), attach the specialist's single hosted
    tool, then let `to_prompt_agent` lift model + tools + instructions into the
    persistable definition. The Action specialist persists instructions-only;
    its local tools are attached client-side at runtime.
    """
    client = FoundryChatClient(
        project_endpoint=settings.project_endpoint,
        model=settings.model,
        credential=build_credential(settings),
        allow_preview=True,
    )
    tools: list[dict] = []
    if spec.tool_builder is not None:
        tool = spec.tool_builder(settings)
        if tool is not None:
            tools.append(tool)

    agent = client.as_agent(
        name=spec.persisted_name,
        instructions=spec.instructions,
        tools=tools or None,
    )
    return to_prompt_agent(agent)


def _latest_instructions(project: AIProjectClient, name: str) -> str | None:
    """Return the latest persisted version's instructions, or None if absent."""
    try:
        versions = list(project.agents.list_versions(name, limit=1, order="desc"))
    except Exception:
        return None
    if not versions:
        return None
    definition = getattr(versions[0], "definition", None)
    return getattr(definition, "instructions", None)


def _tool_summary(definition: PromptAgentDefinition) -> str:
    tools = getattr(definition, "tools", None) or []
    kinds = []
    for t in tools:
        # tools may be SDK models or dicts; read a 'type'/'kind' best-effort.
        k = (
            (t.get("type") or t.get("kind") if isinstance(t, dict) else None)
            or getattr(t, "type", None)
            or getattr(t, "kind", None)
            or type(t).__name__
        )
        kinds.append(str(k))
    return ", ".join(kinds) if kinds else "(no hosted tools — local tools at runtime)"


async def main() -> int:
    base = load_settings()

    # Which mission team(s) to persist. Default: fundraising (back-compat).
    #   MISSIONIQ_TEAM=fundraising | field_response | all
    which = os.getenv("MISSIONIQ_TEAM", "fundraising").strip().lower()
    if which == "all":
        skin_ids = list(TEAMS.keys())
    elif which in TEAMS:
        skin_ids = [which]
    else:
        print(f"Unknown MISSIONIQ_TEAM={which!r}; valid: {', '.join(TEAMS)} or 'all'.")
        return 2

    project = AIProjectClient(
        endpoint=base.project_endpoint,
        credential=build_credential(base),
        allow_preview=True,
    )

    print(f"Project: {base.project_endpoint}")
    print(f"Model:   {base.model}")
    print(f"Teams:   {', '.join(skin_ids)}\n")

    created, skipped = 0, 0
    for skin_id in skin_ids:
        # Effective settings resolve this mission's own Fabric connection + docs
        # index so each specialist's hosted tool points at the right resource.
        settings = settings_for_skin(base, skin_id)
        print(f"── {skin_id}  (fabric: {settings.has_fabric}, "
              f"index: {settings.search_index_name}) ──")
        for spec in TEAMS[skin_id]:
            definition = _build_definition(spec, settings)

            prev = _latest_instructions(project, spec.persisted_name)
            if prev is not None and prev.strip() == spec.instructions.strip():
                print(f"= {spec.persisted_name:26s} unchanged — skipping  [{_tool_summary(definition)}]")
                skipped += 1
                continue

            version = project.agents.create_version(
                spec.persisted_name,
                definition=definition,
                description=f"Mission IQ {spec.key} specialist — {spec.detail}",
            )
            ver = getattr(version, "version", None) or getattr(version, "id", "?")
            print(f"+ {spec.persisted_name:26s} published v{ver}  [{_tool_summary(definition)}]")
            created += 1
        print()

    print(f"Done. {created} published, {skipped} unchanged.")
    print("\nPersisted agents in project:")
    for a in project.agents.list(kind="prompt"):
        nm = getattr(a, "name", "?")
        if str(nm).startswith("MissionIQ-"):
            print(f"  • {nm}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
