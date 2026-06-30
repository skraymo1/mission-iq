"""Live orchestration — the Foundry-connector engine for `live` skins.

Seeded skins reason over local Python tools (offline-safe demo). A *live* skin
(fundraising) instead reasons over **real Foundry connectors**, so the same
question is answered from genuinely connected systems:

  - 🗄️  Fabric Data Agent  → structured donor records   (get_fabric_tool)
  - 🌐  Bing grounding      → live external web facts      (get_bing_grounding_tool)
  - 📄  Azure AI Search     → internal SOPs & policies     (get_azure_ai_search_tool)

The local action tools (draft_outreach / create_task / trigger_workflow) still
run client-side, so the assistant can *act* on what the connectors return — the
cross-source + action story, on real plumbing.
"""
from __future__ import annotations

from azure.identity import AzureCliCredential, DefaultAzureCredential
from agent_framework import ChatContext, chat_middleware
from agent_framework.foundry import FoundryChatClient

from .actions import make_action_tools
from .config import Settings
from .planes.base import RunContext
from .skins.schema import Skin


def build_credential(settings: Settings):
    """Credential for all Foundry calls, pinned to the Foundry resource's tenant.

    On a multi-account dev box `DefaultAzureCredential` may resolve a cached or
    Visual Studio identity in the wrong tenant — Foundry then rejects it with a
    403 (`does not have permissions for .../agents/action`). We therefore prefer
    `AzureCliCredential(tenant_id=...)`, which deterministically uses the
    `az login` account in the Foundry tenant, and fall back to
    `DefaultAzureCredential` only if the CLI isn't available.
    """
    if settings.tenant_id:
        try:
            return AzureCliCredential(tenant_id=settings.tenant_id)
        except Exception:  # pragma: no cover - CLI not present
            pass
    return DefaultAzureCredential()


def build_foundry_client(settings: Settings) -> FoundryChatClient:
    """Chat client bound to the Foundry *project* (Responses API + hosted tools)."""
    return FoundryChatClient(
        project_endpoint=settings.project_endpoint,
        model=settings.model,
        credential=build_credential(settings),
        allow_preview=True,
    )


def connector_planes(settings: Settings) -> list[dict[str, str]]:
    """The live planes that are actually wired, for display + agent construction."""
    planes = [
        {"id": "fabric", "icon": "🗄️", "label": "Fabric Data Agent",
         "detail": "structured donor records", "wired": str(settings.has_fabric)},
        {"id": "docs", "icon": "📄", "label": "Azure AI Search",
         "detail": "internal SOPs & policies", "wired": "True"},
        {"id": "web", "icon": "🌐", "label": "Bing grounding",
         "detail": "live external web", "wired": "True"},
    ]
    return planes


def _hosted_tools(settings: Settings) -> list[dict]:
    """Build the hosted-connector tool payloads (as plain dicts for the Responses API).

    NOTE: the Foundry tool factories return Azure SDK models whose nested members
    are not JSON-serializable on the Responses path; `.as_dict()` flattens them
    into a clean payload the client can send.
    """
    tools: list[dict] = []
    if settings.fabric_connection_id:
        tools.append(
            FoundryChatClient.get_fabric_tool(
                connection_id=settings.fabric_connection_id
            ).as_dict()
        )
    tools.append(
        FoundryChatClient.get_azure_ai_search_tool(
            index_connection_id=settings.search_connection_id,
            index_name=settings.search_index_name,
            query_type="simple",
            top_k=4,
        ).as_dict()
    )
    tools.append(
        FoundryChatClient.get_bing_grounding_tool(
            connection_id=settings.bing_connection_id, count=4
        ).as_dict()
    )
    return tools


def build_live_instructions(skin: Skin, settings: Settings) -> str:
    fabric_line = (
        "- 🗄️ Fabric Data Agent — the system of record. Ask it for donors, giving "
        "history, wealth/capacity ratings, campaigns. It writes its own queries over "
        "the gold fundraising model; just ask in plain language."
        if settings.has_fabric
        else "- 🗄️ Fabric Data Agent — (not connected this session; rely on the other planes)."
    )
    return f"""You are Mission IQ, a mission-control assistant for a non-profit running the
"{skin.name}" mission — answering from REAL connected systems, not guesses.

This mission's frame (the five slots you optimize within):
- DEMAND: {skin.demand.strip()}
- SUPPLY: {skin.supply.strip()}
- GUARDRAILS: {skin.guardrails.strip()}
- IMPACT: {skin.impact.strip()}
- FEEDBACK: {skin.feedback.strip()}

Your connected planes (each a real tool):
{fabric_line}
- 📄 Azure AI Search — internal SOPs, gift acceptance policy, stewardship rules,
  year-end playbook. Use it to apply the organization's own guardrails.
- 🌐 Bing — live external facts (IRS deadlines, sector giving trends, news).

And action tools: draft_outreach, create_task, trigger_workflow.

How to operate:
1. Pull from EVERY plane that's relevant. A donor-targeting question usually means
   Fabric (who, capacity, recency) AND AI Search (does policy/cadence allow the ask)
   AND sometimes Bing (year-end timing, deductibility).
2. Apply the guardrails from the docs: honor do-not-solicit, contact preferences,
   anonymity, and the one-major-ask-per-quarter cap. Call out conflicts explicitly.
3. Rank by impact (dollars/pledges per gift-officer hour; reactivation lift) and say
   why each pick made the cut. Use real names/figures the tools return — never invent.
4. Turn the answer into progress: when the user should reach someone or set a next
   step, call the action tools to stage outreach/tasks/workflows.
5. Be concise and decision-ready. Lead with the answer. Note caveats briefly.
"""


def build_live_agent(skin: Skin, ctx: RunContext, settings: Settings, client: FoundryChatClient):
    tools = _hosted_tools(settings) + make_action_tools(skin, ctx)
    return client.as_agent(
        name="MissionIQ",
        instructions=build_live_instructions(skin, settings),
        tools=tools,
        middleware=[make_attribution_middleware(ctx)],
    )


def _ann_get(ann, key: str) -> str:
    """Read a field from an annotation, falling back to its raw citation object.

    Foundry annotations arrive as dicts whose top-level `url`/`title` are often
    empty; the populated values live on the nested `raw_representation`
    (an AnnotationURLCitation). Check both.
    """
    if isinstance(ann, dict):
        val = ann.get(key)
        if val:
            return str(val)
        raw = ann.get("raw_representation")
    else:
        val = getattr(ann, key, None)
        if val:
            return str(val)
        raw = getattr(ann, "raw_representation", None)
    if raw is not None:
        return str(getattr(raw, key, "") or "")
    return ""


# Map a Responses-API output-item type to the plane that produced it. The item
# `.type` (e.g. "azure_ai_search_call", "bing_grounding_call") names the hosted
# connector that actually ran this turn — the most honest "which source was used"
# signal, and one that survives even when the model drops inline citations.
_PLANE_BY_ITEM: list[tuple[str, tuple[str, str, str]]] = [
    ("azure_ai_search", ("Docs · AI Search", "📄", "internal SOPs & policies")),
    ("bing", ("Web · Bing", "🌐", "live external web")),
    ("web_search", ("Web · Bing", "🌐", "live external web")),
    ("fabric", ("Fabric Data Agent", "🗄️", "structured donor records")),
]


def _item_plane(item_type: str) -> tuple[str, str, str] | None:
    t = (item_type or "").lower()
    for needle, plane in _PLANE_BY_ITEM:
        if needle in t:
            return plane
    return None


def make_attribution_middleware(ctx: RunContext):
    """Chat middleware that records which connectors actually ran, per turn.

    Hosted connectors execute server-side, so they don't call `ctx.touch`
    themselves — and when a local action tool fires in the same turn, the inline
    citations get dropped from the final result. We instead read each turn's raw
    Responses output items: their `.type` names the connector that ran. We also
    opportunistically pull citation titles/urls for a richer chip label.
    """
    seen: set[str] = set()

    @chat_middleware
    async def _attribution(context: ChatContext, call_next) -> None:
        await call_next()
        res = context.result
        if res is None:
            return

        # Best-effort: richer detail from any inline citations present this turn.
        detail_for: dict[str, str] = {}
        for msg in getattr(res, "messages", []) or []:
            for c in getattr(msg, "contents", []) or []:
                for ann in getattr(c, "annotations", None) or []:
                    url = _ann_get(ann, "url")
                    title = _ann_get(ann, "title")
                    low = url.lower()
                    if "search.windows.net" in low and title:
                        detail_for.setdefault("Docs · AI Search", title)
                    elif low.startswith("http"):
                        detail_for.setdefault("Web · Bing", title or url)

        raw = getattr(res, "raw_representation", None)
        for item in getattr(raw, "output", None) or []:
            plane = _item_plane(getattr(item, "type", None) or type(item).__name__)
            if plane is None:
                continue
            label, icon, default_detail = plane
            if label in seen:
                continue
            seen.add(label)
            ctx.touch(label, icon, detail_for.get(label, default_detail))

    return _attribution
