"""Magentic orchestration — the in-app multi-agent engine for live skins.

Where `live.py` runs ONE Foundry agent holding every connector, this module runs
the **team** of Foundry-persisted specialists under a Magentic manager. The
manager (gpt-5.4) plans, delegates to DonorData / Policy / Web / Action, tracks a
progress ledger, replans on stalls, and synthesizes one final answer — the
Magentic-One pattern, over real Foundry agents.

We surface the orchestration for the demo by recording, into the RunContext's
`MagenticTrace`, the manager's plan, each progress-ledger step, and every
specialist's turn — so the cockpit can show *how* the answer was reached, not
just the answer.

Participants are `FoundryAgent` handles to the agents published by
`scripts/provision_foundry_agents.py`; the Action specialist additionally gets
the client-side action tools (which can't be persisted server-side).
"""
from __future__ import annotations

import os
from typing import Any

from agent_framework.foundry import FoundryAgent
from agent_framework_orchestrations import (
    MagenticBuilder,
    MagenticOrchestratorEvent,
    MagenticOrchestratorEventType,
)

from .actions import make_action_tools
from .agents_spec import (
    AgentSpec,
    MANAGER_NAME,
    active_team,
    manager_instructions,
    spec_by_key,
)
from .config import Settings
from .live import build_credential, build_foundry_client, make_attribution_middleware
from .planes.base import AgentTurn, MagenticTrace, RunContext
from .skins.schema import Skin

DEBUG = os.getenv("MISSIONIQ_MAGENTIC_DEBUG", "0") == "1"


# --- participant + manager construction ------------------------------------

def build_participant(
    spec: AgentSpec, skin: Skin, ctx: RunContext, settings: Settings
):
    """A runnable Magentic node for one specialist.

    Connector specialists (DonorData/Policy/Web) are handles to the **persisted**
    Foundry agents (`FoundryAgent`, `agent_name=...`); their hosted tools live in
    the published definition and the attribution middleware records which
    connector actually fired.

    The Action specialist is different: its tools are *local* Python functions, and
    Foundry rejects a `tools` payload when a persisted agent is targeted
    (`400 invalid_payload: Not allowed when agent is specified`). So we build it as a
    client-side agent on the same model, carrying the action tools, so they execute
    in-process and stage proposals into the RunContext. It still exists in the
    portal (for the Group-chat workflow); only the runtime handle differs.
    """
    if spec.local_action_tools:
        client = build_foundry_client(settings)
        return client.as_agent(
            name=spec.key,
            instructions=spec.instructions,
            tools=make_action_tools(skin, ctx),
        )
    return FoundryAgent(
        project_endpoint=settings.project_endpoint,
        agent_name=spec.persisted_name,
        credential=build_credential(settings),
        allow_preview=True,
        name=spec.key,
        middleware=[make_attribution_middleware(ctx)],
    )


def build_manager_agent(skin: Skin, settings: Settings):
    """The Magentic manager — gpt-5.4 reasoning over the team. No tools itself."""
    client = build_foundry_client(settings)
    return client.as_agent(
        name=MANAGER_NAME,
        instructions=manager_instructions(skin.name),
    )


def build_workflow(skin: Skin, ctx: RunContext, settings: Settings):
    """Assemble the Magentic workflow over the active specialist team."""
    participants = [
        build_participant(spec, skin, ctx, settings)
        for spec in active_team(settings)
    ]
    manager = build_manager_agent(skin, settings)
    return MagenticBuilder(
        participants=participants,
        manager_agent=manager,
        intermediate_output_from="all_other",
        max_round_count=int(os.getenv("MISSIONIQ_MAGENTIC_MAX_ROUNDS", "16")),
        max_stall_count=int(os.getenv("MISSIONIQ_MAGENTIC_MAX_STALL", "4")),
        max_reset_count=int(os.getenv("MISSIONIQ_MAGENTIC_MAX_RESET", "3")),
    ).build()


# --- event helpers ---------------------------------------------------------

def _message_text(msg: Any) -> str:
    """Best-effort plain text from a Message / content list / string / response."""
    if msg is None:
        return ""
    if isinstance(msg, str):
        return msg
    if isinstance(msg, (list, tuple)):
        return "\n".join(t for t in (_message_text(m) for m in msg) if t).strip()
    text = getattr(msg, "text", None)
    if text:
        return str(text)
    # AgentResponse / AgentRunResponse carry a .messages list.
    msgs = getattr(msg, "messages", None)
    if msgs:
        return _message_text(list(msgs))
    nested = getattr(msg, "agent_run_response", None)
    if nested is not None:
        return _message_text(nested)
    parts: list[str] = []
    for c in getattr(msg, "contents", None) or []:
        t = getattr(c, "text", None)
        if t:
            parts.append(str(t))
        elif isinstance(c, str):
            parts.append(c)
    return "\n".join(parts).strip()


def _icon_for(name: str) -> str:
    spec = spec_by_key(name)
    return spec.icon if spec else "🧠"


# Each connector specialist owns exactly one plane. The per-turn attribution
# middleware records which hosted tool fired on the Responses path, but persisted
# Foundry agents (Agents API) surface a different raw shape, so that signal can be
# silent here. We therefore also attribute at the *agent* grain: if a connector
# specialist contributed a substantive turn, its one plane was used. Labels match
# `live._PLANE_BY_ITEM` exactly so the two paths dedup cleanly via `ctx.touch`.
_SOURCE_BY_KEY: dict[str, tuple[str, str, str]] = {
    "DonorData": ("Fabric Data Agent", "🗄️", "structured donor records"),
    "Policy": ("Docs · AI Search", "📄", "internal SOPs & policies"),
    "Web": ("Web · Bing", "🌐", "live external web"),
}


def _handle_orchestrator(data: MagenticOrchestratorEvent, trace: MagenticTrace) -> None:
    et = data.event_type
    content = data.content
    if et in (MagenticOrchestratorEventType.PLAN_CREATED,
              MagenticOrchestratorEventType.REPLANNED):
        plan = _message_text(content)
        if et == MagenticOrchestratorEventType.REPLANNED:
            trace.replans += 1
            trace.ledger.append("↻ Replanned (stall) — manager revised the plan.")
        trace.plan = plan
    elif et == MagenticOrchestratorEventType.PROGRESS_LEDGER_UPDATED:
        trace.rounds += 1
        nxt = getattr(getattr(content, "next_speaker", None), "answer", "") or ""
        instr = getattr(getattr(content, "instruction_or_question", None), "answer", "") or ""
        if nxt or instr:
            icon = _icon_for(str(nxt))
            line = f"{icon} → {nxt}: {instr}" if nxt else f"🧠 {instr}"
            trace.ledger.append(line.strip())


# --- run -------------------------------------------------------------------

async def run_magentic(
    skin: Skin, ctx: RunContext, settings: Settings, question: str
) -> str:
    """Run one question through the Magentic team; return the final answer text.

    Populates `ctx.magentic` (plan, ledger, per-specialist turns), `ctx.sources`
    (via each participant's attribution middleware), and `ctx.actions` (via the
    Action specialist's tools).

    Event mapping (agent_framework `WorkflowEvent.type` discriminator):
      - `data` is a `MagenticOrchestratorEvent` -> manager plan / progress ledger.
      - streaming `*Update` data (per `executor_id`) -> accumulate clean turn text.
      - `type == "executor_completed"` w/ list data -> fallback per-agent turn text.
      - `type == "output"` -> the manager's synthesized final answer.
    """
    trace = MagenticTrace()
    ctx.magentic = trace
    workflow = build_workflow(skin, ctx, settings)

    final_text = ""
    # Clean per-author text rebuilt from streamed deltas (concatenate, no glue).
    parts_by_author: dict[str, str] = {}
    # Fallback per-author text from completed message lists.
    list_by_author: dict[str, str] = {}

    async for event in workflow.run(question, stream=True):
        data = getattr(event, "data", None)
        etype = getattr(event, "type", None)
        author = getattr(event, "executor_id", None) or ""

        if isinstance(data, MagenticOrchestratorEvent):
            if DEBUG:
                print(f"[ev] type={etype!s:14s} ORCH {data.event_type}")
            _handle_orchestrator(data, trace)
            continue

        is_update = type(data).__name__.endswith("Update")

        # Reassemble each speaker's text from its streamed token deltas — this is
        # the cleanest source (the completed list events arrive token-fragmented).
        if is_update and author:
            piece = _message_text(data)
            if piece:
                parts_by_author[author] = parts_by_author.get(author, "") + piece
            continue

        if DEBUG:
            print(f"[ev] type={etype!s:18s} data={type(data).__name__:22s} "
                  f"author={author!r} text={_message_text(data)[:70]!r}")

        if etype == "output":
            txt = _message_text(data)
            if txt:
                final_text = txt
            continue

        if etype in ("executor_completed", "intermediate") and author:
            txt = _message_text(data)
            if txt:
                list_by_author[author] = txt

    # Record each specialist that actually contributed, in team order. Prefer the
    # delta-assembled text; fall back to the completed-list text. For connector
    # specialists, attribute their owning plane to ctx.sources (the middleware's
    # per-turn signal can be silent on the persisted-agent path).
    for spec in active_team(settings):
        txt = parts_by_author.get(spec.key) or list_by_author.get(spec.key)
        if txt and txt.strip():
            trace.turns.append(AgentTurn(name=spec.key, icon=spec.icon, text=txt.strip()))
            source = _SOURCE_BY_KEY.get(spec.key)
            if source:
                ctx.touch(*source)

    # The manager streams its final synthesis as deltas too; if no explicit output
    # event carried text, fall back to the orchestrator's assembled text.
    if not final_text:
        final_text = (parts_by_author.get("magentic_orchestrator", "")
                      or list_by_author.get("magentic_orchestrator", "")).strip()

    # Robustness: the manager can terminate on stall/reset budget (e.g. a transient
    # Fabric backend error starves the team of data). In that case the "output" event
    # carries a bare sentinel, not an answer — never surface that to the cockpit.
    # Synthesize a best-effort answer from whatever the specialists DID contribute.
    if _is_terminal_sentinel(final_text):
        final_text = _fallback_answer(trace, final_text)

    return final_text or "(no answer produced)"


_TERMINATION_MARKERS = (
    "workflow terminated",
    "maximum reset count",
    "maximum stall count",
    "maximum round count",
)


def _is_terminal_sentinel(text: str) -> bool:
    low = (text or "").strip().lower()
    if not low:
        return False
    return any(m in low for m in _TERMINATION_MARKERS)


def _fallback_answer(trace: MagenticTrace, sentinel: str) -> str:
    """Assemble a usable answer from the specialists' turns when the manager
    terminated before synthesizing. Honest about the degradation, but still gives
    the operator the substance the team gathered plus any staged actions."""
    lines: list[str] = [
        "⚠️ The team didn't fully converge on a single synthesized answer this run, "
        "so here is the best synthesis from what each specialist gathered:",
        "",
    ]
    if trace.turns:
        for turn in trace.turns:
            body = turn.text.strip()
            if body:
                lines.append(f"{turn.icon} {turn.name}: {body}")
                lines.append("")
    else:
        lines.append("No specialist returned usable content this run.")
        lines.append("")
    lines.append(
        "Next step: re-run the question (the unavailable source is usually "
        "transient), or proceed with the staged tasks below for human review."
    )
    return "\n".join(lines).strip()
