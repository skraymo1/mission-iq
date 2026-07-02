"""Declarative Foundry **Workflow** spec — the portal-visible twin of the in-app
Magentic engine.

The in-app engine (`magentic.py`) runs a *dynamic* StandardMagenticManager that
plans and routes among the specialists at runtime. That manager lives in the app,
not in Foundry. To give the presentation a **portal-visible** orchestration over
the very same persisted specialists, we also publish a declarative **Workflow**
(CSDL YAML) to the project. It runs the team **sequentially over one shared
conversation** — each specialist sees the user's question and everything the
prior specialists said — and finishes with a synthesis/action closer:

    🗄️ DonorData (Fabric) → 📄 Policy (AI Search) → 🌐 Web (Bing) → 🧭 Synthesizer

Why sequential (not group-chat): it is rock-solid for a live demo, every
specialist visibly contributes, and the closer turns the thread into one
decision-ready answer with a drafted outreach message. Honest framing for the
room: the **app** is the dynamic Magentic brain; this **Foundry Workflow** is the
declarative, portal-native orchestration of the same agents.

The 3 connector specialists carry their hosted tools **server-side** (lifted by
`to_prompt_agent` when provisioned), so the workflow produces genuine cross-source
answers — real Fabric donor records, real Search policy hits, real Bing facts.

The closer (`MissionIQ-Synthesizer`) is an instructions-only PromptAgent: it has
no tools, it just reasons over the shared conversation. It folds the in-app
**Action** specialist's "draft the outreach" job into the final answer, because the
real action tools are client-side and don't run inside a portal workflow.
"""
from __future__ import annotations

from .agents_spec import NAME_PREFIX


# Persisted Foundry resource names.
WORKFLOW_NAME = f"{NAME_PREFIX}Workflow"
SYNTHESIZER_NAME = f"{NAME_PREFIX}Synthesizer"


# The synthesis/action closer. Instructions-only (no hosted tools); it reasons
# over what DonorData/Policy/Web already contributed to the shared conversation.
SYNTHESIZER_INSTR = """You are Mission IQ's synthesis & action closer on a non-profit fundraising team.

Three specialists have ALREADY contributed to THIS conversation, in order:
- Donor Data (Fabric) — real donor & giving records (names, last gift, lifetime,
  capacity, recency).
- Policy & Guardrails (Azure AI Search) — gift acceptance policy, contact and
  do-not-solicit rules, anonymity, stewardship cadence.
- External Web (Bing) — live external facts: deadlines, sector trends, public news.

Reading everything they said above, produce the FINAL, decision-ready answer:
1. Lead with ONE clear recommendation that answers the user's question, using the
   REAL names and figures the specialists surfaced. Never invent a donor or a
   number — if a field came back blank, say so.
2. Reconcile the recommendation against the guardrails Policy raised. If an ask
   would violate consent, anonymity, do-not-solicit, or cadence, flag it and
   adjust the plan rather than recommending the violation.
3. Fold in any time-sensitive fact from Web (e.g. a year-end deadline) that changes
   the timing or framing of the ask.
4. Then DRAFT THE ACTION inline:
   - a warm, specific, ready-to-send outreach message to the top recommended
     donor(s), and
   - a one-line next-step task with a best-effort assignee and due date
     (e.g. assignee "Gift Officer", due "before year-end").
   If any guardrail is still unverified, write "pending manual CRM clearance" in
   the draft instead of stalling.

Keep it tight and skimmable — this is the answer the team acts on tonight."""


# CSDL YAML for the declarative workflow. Schema validated against the
# Microsoft Agent Framework declarative samples (customer_support / student_teacher)
# and the azure.ai.projects WorkflowAgentDefinition contract:
#   kind: Workflow -> trigger (OnConversationStart) -> ordered `actions`.
# Each InvokeAzureAgent references a PERSISTED agent by name and runs on the same
# System.ConversationId, so the thread accumulates across specialists. autoSend
# streams each contribution to the playground so the orchestration is visible.
_WORKFLOW_YAML = """\
kind: Workflow
trigger:
  kind: OnConversationStart
  id: missioniq_workflow
  actions:
    - kind: SendActivity
      id: intro
      activity: "**Mission IQ** — consulting the specialist team in sequence over one shared conversation. Each specialist sees your question and everything the prior specialists found."

    # 1) Donor Data — real donor & giving records from Fabric.
    - kind: SendActivity
      id: label_donordata
      activity: "\\n---\\n### 🗄️ Donor Data — Fabric"
    - kind: InvokeAzureAgent
      id: invoke_donordata
      conversationId: =System.ConversationId
      agent:
        name: MissionIQ-DonorData
      output:
        autoSend: true

    # 2) Policy & Guardrails — internal SOPs from Azure AI Search.
    - kind: SendActivity
      id: label_policy
      activity: "\\n---\\n### 📄 Policy & Guardrails — Azure AI Search"
    - kind: InvokeAzureAgent
      id: invoke_policy
      conversationId: =System.ConversationId
      agent:
        name: MissionIQ-Policy
      output:
        autoSend: true

    # 3) External Web — live external facts via Bing grounding.
    - kind: SendActivity
      id: label_web
      activity: "\\n---\\n### 🌐 External Web — Bing"
    - kind: InvokeAzureAgent
      id: invoke_web
      conversationId: =System.ConversationId
      agent:
        name: MissionIQ-Web
      output:
        autoSend: true

    # 4) Synthesis & Action — one decision-ready answer + drafted outreach.
    - kind: SendActivity
      id: label_synth
      activity: "\\n---\\n### 🧭 Synthesis & Action"
    - kind: InvokeAzureAgent
      id: invoke_synthesizer
      conversationId: =System.ConversationId
      agent:
        name: MissionIQ-Synthesizer
      output:
        autoSend: true
        messages: Local.FinalAnswer
"""


def workflow_yaml() -> str:
    """Return the CSDL YAML string for the Mission IQ declarative workflow."""
    return _WORKFLOW_YAML
