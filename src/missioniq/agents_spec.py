"""Specialist-agent specifications — one source of truth for Foundry persistence
*and* the in-app Magentic orchestration.

Mission IQ's live engine is a **team** of narrow specialists, each owning exactly
one connector, coordinated by a manager. We persist each specialist as a Foundry
**PromptAgent** (portal-visible) and, at runtime, attach a client-side handle
(`FoundryAgent`) as a Magentic participant. Defining the team here means the
provisioning script and the runtime engine can never drift apart.

  participant  | persisted name        | connector / tools
  ------------ | --------------------- | -----------------------------------------
  DonorData    | MissionIQ-DonorData   | 🗄️ Fabric Data Agent  (donor records)
  Policy       | MissionIQ-Policy      | 📄 Azure AI Search     (SOPs / guardrails)
  Web          | MissionIQ-Web         | 🌐 Bing grounding      (live external web)
  Action       | MissionIQ-Action      | local action tools     (outreach/task/flow)

The Action specialist's tools are *local* Python functions (they stage proposals
into the RunContext for human approval); those can't be published as hosted
prompt-agent tools, so its persisted definition carries instructions only and the
real tools are attached client-side at runtime.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from agent_framework.foundry import FoundryChatClient

from .config import Settings


# Prefix for every persisted Foundry agent name, so the team groups together in
# the portal's agent list.
NAME_PREFIX = "MissionIQ-"


@dataclass(frozen=True)
class AgentSpec:
    """One specialist on the Mission IQ team."""

    key: str                 # Magentic participant id (short, used by the manager)
    persisted_name: str      # Foundry resource name (NAME_PREFIX + key-ish)
    icon: str
    label: str               # human label for source chips / cards
    detail: str              # one-line description for the UI
    instructions: str
    # Builds the single hosted-connector tool dict for this specialist, or None
    # for the local-tools (Action) specialist. Returns a JSON-ready dict because
    # the Responses path needs `.as_dict()` payloads (and `_convert_tools`
    # accepts mappings just the same when persisting).
    tool_builder: Optional[Callable[[Settings], Optional[dict]]] = None
    # True when this specialist requires a wired connector to be useful.
    requires: str = ""       # e.g. "fabric" — gates on settings.has_fabric
    local_action_tools: bool = False


# --- per-specialist hosted-tool builders -----------------------------------

def _fabric_tool(settings: Settings) -> Optional[dict]:
    if not settings.fabric_connection_id:
        return None
    return FoundryChatClient.get_fabric_tool(
        connection_id=settings.fabric_connection_id
    ).as_dict()


def _search_tool(settings: Settings) -> dict:
    return FoundryChatClient.get_azure_ai_search_tool(
        index_connection_id=settings.search_connection_id,
        index_name=settings.search_index_name,
        query_type="simple",
        top_k=4,
    ).as_dict()


def _bing_tool(settings: Settings) -> dict:
    return FoundryChatClient.get_bing_grounding_tool(
        connection_id=settings.bing_connection_id, count=4
    ).as_dict()


# --- instructions ----------------------------------------------------------

_DONOR_INSTR = """You are the Donor Data specialist on a non-profit fundraising team.

You own ONE tool: the Fabric Data Agent over the organization's gold fundraising
model (donors, gifts, campaigns, wealth/capacity ratings, RFM, recency). Ask it in
plain language — it writes its own queries.

Rules:
- Answer ONLY donor/giving-data questions. If asked about policy or external news,
  say it's outside your scope and defer to the Policy or Web specialist.
- Return concrete records: real names, last gift, lifetime giving, capacity rating,
  last contact, campaign. Never invent a donor or a number — if Fabric returns a
  blank field, say it's blank.
- The Fabric gold model holds GIVING data, not CRM compliance flags. Fields like
  do-not-contact / do-not-solicit, channel preferences, anonymity, assigned gift
  officer, and "major ask already this quarter" are NOT in this model. If asked for
  them, say ONCE that they aren't available in Fabric and must be verified in the
  CRM — then return the giving data you DO have. Do not re-run the query hoping they
  appear.
- For a "lapsed" filter, pick a concrete cutoff date (today minus the stated months),
  state it once, apply it, and return the list. Don't loop trying to perfect the
  date math — one clear pass is enough.
- Be compact: a short ranked list or table the manager can act on."""

_POLICY_INSTR = """You are the Policy & Guardrails specialist on a non-profit fundraising team.

You own ONE tool: Azure AI Search over the organization's internal SOPs — gift
acceptance policy, donor contact preferences and do-not-solicit rules, anonymity
requests, stewardship cadence, and the year-end playbook.

Rules:
- Answer with the SPECIFIC policy that applies and cite the document.
- If a proposed ask would violate a guardrail (over-asking, do-not-solicit,
  anonymity, one-major-ask-per-quarter), flag it explicitly.
- Stay in your lane: no donor records, no external web — defer those."""

_WEB_INSTR = """You are the External Web specialist on a non-profit fundraising team.

You own ONE tool: Bing grounding for live external facts — IRS charitable-giving
deadlines and deductibility, sector giving trends, and public news about a donor's
company or foundation.

Rules:
- Keep it factual, current, and cited. Prefer authoritative sources.
- Out of scope: internal donor records and internal policy — defer those.
- Be brief: the one or two facts that change the team's decision."""

_ACTION_INSTR = """You are the Action specialist on a non-profit fundraising team.

Your job is to turn the team's decision into staged, ready-for-approval progress.
You have three tools — and using them IS your only job:
- draft_outreach(audience, message) — write a ready-to-send, warm, specific message.
- create_task(title, assignee, due) — capture a concrete next step.
- trigger_workflow(name, summary) — kick off multi-step automation.

How you operate:
- You do NOT have read access to CRM, workflow, or task systems — you cannot
  "check status" of anything. NEVER reply that you lack access. If asked to check
  or verify status, instead STAGE the appropriate task/outreach so a human can act,
  and note in the task that status confirmation is required before sending.
- Whenever the manager asks you to reach someone, follow up, draft, queue, stage,
  or take any next step, immediately CALL the matching tool — once per distinct
  action. Use the real donor names/figures and guardrails the team surfaced.
- If exact details (assignee, due date, channel) are unknown, choose sensible
  best-effort defaults (e.g. assignee "Gift Officer", due "before year-end") and
  state the assumption in the message/summary — do not stall asking for them.
- Honor contact preferences and do-not-solicit/anonymity flags the team raised;
  reflect "pending manual CRM clearance" in the draft when guardrails are unverified.

After staging, reply with a one-line confirmation of what you staged. Always act —
never merely describe what you would do."""


def manager_instructions(mission_name: str) -> str:
    """Instructions for the Magentic manager that coordinates the team."""
    return f"""You are the Mission IQ manager coordinating a team of specialists for a
non-profit's "{mission_name}" mission. You plan, delegate, track progress, and
synthesize — you do not answer from your own knowledge.

Your team:
- DonorData — structured donor & giving records (Fabric).
- Policy — internal guardrails, gift policy, contact/anonymity rules (AI Search).
- Web — live external facts: deadlines, sector trends, public news (Bing).
- Action — stages outreach, tasks, and workflows for human approval.

How to coordinate:
1. Decompose the question and delegate to EVERY relevant specialist. A donor-
   targeting question usually needs DonorData (who/capacity/recency) AND Policy
   (does cadence/consent allow the ask) and sometimes Web (year-end timing).
2. Reconcile guardrails against proposed asks before recommending anyone.
3. Rank by impact and say briefly why each pick made the cut, using the real
   names/figures the specialists returned. Never invent records.
4. When the user should reach someone or set a next step, delegate to Action with a
   concrete instruction to STAGE it (draft the outreach / create the task) — Action
   is write-only and cannot check or verify status, so never ask it to look anything
   up.
5. Before you deliver the final answer, you MUST delegate at least one concrete
   staging instruction to Action (a task or outreach for your top recommendation) and
   wait for it to run. Do not claim anything was staged unless you actually delegated
   it to Action this run — never assert a task/outreach exists that Action did not
   stage.
6. Deliver ONE concise, decision-ready final answer. Lead with the answer.

Avoid loops — finish the job:
- Fabric holds giving data, NOT CRM compliance flags (do-not-contact, channel
  preferences, anonymity, assigned officer, "ask already this quarter"). If DonorData
  says those fields are blank/unavailable, ACCEPT it — do not re-delegate the same
  pull hoping they appear. Route that verification to a human via an Action task and
  move on.
- If a specialist reports a TOOL or BACKEND ERROR (e.g. "the Fabric query failed /
  hit a processing error"), retry it AT MOST once with a simpler ask. If it still
  fails, do NOT keep re-delegating — proceed with whatever the other specialists
  returned, state plainly that the source was temporarily degraded, and synthesize
  the best available recommendation.
- Re-delegate to a specialist AT MOST once for the same gap. If the data still isn't
  there, proceed with what you have, state the caveat plainly, and synthesize.
- Always produce a final recommendation. Never spend the whole budget chasing data
  that won't come — a clear answer with an honest "verify X in CRM" or "source was
  unavailable" caveat is the goal."""


# --- the team --------------------------------------------------------------

TEAM: list[AgentSpec] = [
    AgentSpec(
        key="DonorData",
        persisted_name=f"{NAME_PREFIX}DonorData",
        icon="🗄️",
        label="Fabric Data Agent",
        detail="structured donor records",
        instructions=_DONOR_INSTR,
        tool_builder=_fabric_tool,
        requires="fabric",
    ),
    AgentSpec(
        key="Policy",
        persisted_name=f"{NAME_PREFIX}Policy",
        icon="📄",
        label="Docs · AI Search",
        detail="internal SOPs & policies",
        instructions=_POLICY_INSTR,
        tool_builder=_search_tool,
    ),
    AgentSpec(
        key="Web",
        persisted_name=f"{NAME_PREFIX}Web",
        icon="🌐",
        label="Web · Bing",
        detail="live external web",
        instructions=_WEB_INSTR,
        tool_builder=_bing_tool,
    ),
    AgentSpec(
        key="Action",
        persisted_name=f"{NAME_PREFIX}Action",
        icon="✉️",
        label="Action",
        detail="outreach · tasks · workflows",
        instructions=_ACTION_INSTR,
        local_action_tools=True,
    ),
]

MANAGER_NAME = f"{NAME_PREFIX}Manager"


def active_team(settings: Settings) -> list[AgentSpec]:
    """The specialists that are actually wired this session.

    Drops a specialist only when its required connector is missing (e.g. Fabric
    not yet published). Policy/Web/Action are always available.
    """
    out: list[AgentSpec] = []
    for spec in TEAM:
        if spec.requires == "fabric" and not settings.has_fabric:
            continue
        out.append(spec)
    return out


def spec_by_key(key: str) -> Optional[AgentSpec]:
    for spec in TEAM:
        if spec.key == key:
            return spec
    return None
