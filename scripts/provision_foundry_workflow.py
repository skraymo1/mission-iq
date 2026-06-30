r"""Provision the Mission IQ **declarative Workflow** (and its synthesis closer) as
persisted Foundry resources — the portal-visible twin of the in-app Magentic engine.

Run AFTER `provision_foundry_agents.py` (the workflow references the persisted
connector specialists MissionIQ-DonorData / -Policy / -Web by name):

    $env:PYTHONIOENCODING="utf-8"; $env:PYTHONUTF8="1"; $env:PYTHONPATH="src"
    .\.venv\Scripts\python.exe scripts\provision_foundry_workflow.py

It publishes two resources, idempotently (only a changed definition makes a new
version):

  • MissionIQ-Synthesizer  — instructions-only PromptAgent; the synthesis/action
                             closer that turns the team's thread into one
                             decision-ready answer + drafted outreach.
  • MissionIQ-Workflow     — WorkflowAgentDefinition (CSDL YAML); runs
                             DonorData → Policy → Web → Synthesizer sequentially
                             over one shared conversation.

Both appear in the Foundry portal (Agents / Workflows) and can be test-run from the
portal playground or VS Code remote playground.
"""
from __future__ import annotations

import asyncio
import sys

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition, WorkflowAgentDefinition
from agent_framework.foundry import FoundryChatClient, to_prompt_agent

from missioniq.config import load_settings
from missioniq.live import build_credential
from missioniq.workflow_spec import (
    SYNTHESIZER_INSTR,
    SYNTHESIZER_NAME,
    WORKFLOW_NAME,
    workflow_yaml,
)


def _build_synth_definition(settings) -> PromptAgentDefinition:
    """Instructions-only PromptAgent for the synthesis/action closer (no tools)."""
    client = FoundryChatClient(
        project_endpoint=settings.project_endpoint,
        model=settings.model,
        credential=build_credential(settings),
        allow_preview=True,
    )
    agent = client.as_agent(name=SYNTHESIZER_NAME, instructions=SYNTHESIZER_INSTR)
    return to_prompt_agent(agent)


def _latest_definition(project: AIProjectClient, name: str):
    """Return the latest persisted version's definition, or None if absent."""
    try:
        versions = list(project.agents.list_versions(name, limit=1, order="desc"))
    except Exception:
        return None
    if not versions:
        return None
    return getattr(versions[0], "definition", None)


def _norm(text: str | None) -> str:
    return (text or "").strip()


async def main() -> int:
    settings = load_settings()
    project = AIProjectClient(
        endpoint=settings.project_endpoint,
        credential=build_credential(settings),
        allow_preview=True,
    )

    print(f"Project: {settings.project_endpoint}")
    print(f"Model:   {settings.model}\n")

    # --- 1) Synthesis/action closer (PromptAgent) --------------------------
    synth_def = _build_synth_definition(settings)
    prev = _latest_definition(project, SYNTHESIZER_NAME)
    prev_instr = _norm(getattr(prev, "instructions", None))
    if prev_instr and prev_instr == _norm(SYNTHESIZER_INSTR):
        print(f"= {SYNTHESIZER_NAME:24s} unchanged — skipping")
    else:
        v = project.agents.create_version(
            SYNTHESIZER_NAME,
            definition=synth_def,
            description="Mission IQ synthesis & action closer — one decision-ready answer + drafted outreach.",
        )
        ver = getattr(v, "version", None) or getattr(v, "id", "?")
        print(f"+ {SYNTHESIZER_NAME:24s} published v{ver}")

    # --- 2) Declarative workflow (WorkflowAgentDefinition) -----------------
    yaml_str = workflow_yaml()
    wf_def = WorkflowAgentDefinition(workflow=yaml_str)
    prev_wf = _latest_definition(project, WORKFLOW_NAME)
    prev_yaml = _norm(getattr(prev_wf, "workflow", None))
    if prev_yaml and prev_yaml == _norm(yaml_str):
        print(f"= {WORKFLOW_NAME:24s} unchanged — skipping")
    else:
        v = project.agents.create_version(
            WORKFLOW_NAME,
            definition=wf_def,
            description="Mission IQ declarative workflow — DonorData → Policy → Web → Synthesizer over one shared conversation.",
        )
        ver = getattr(v, "version", None) or getattr(v, "id", "?")
        print(f"+ {WORKFLOW_NAME:24s} published v{ver}")

    # --- verify -------------------------------------------------------------
    print("\nPersisted Mission IQ agents in project:")
    for a in project.agents.list(kind="prompt"):
        nm = getattr(a, "name", "?")
        if str(nm).startswith("MissionIQ-"):
            print(f"  • {nm}")
    print("\nPersisted Mission IQ workflows in project:")
    try:
        for a in project.agents.list(kind="workflow"):
            nm = getattr(a, "name", "?")
            if str(nm).startswith("MissionIQ-"):
                print(f"  • {nm}")
    except Exception as exc:  # pragma: no cover - listing API shape may vary
        print(f"  (workflow listing unavailable: {exc})")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
