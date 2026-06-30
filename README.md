# 🧭 Mission IQ

**One assistant. Every mission. Reasons across your data — and acts.**

Picture a volunteer coordinator the night a hurricane hits. She asks one
question — *"Who can I get to the Houston shelter tonight?"* — and in seconds the
assistant pulls live volunteer records, figures out who's nearby and reliable,
checks current road closures, applies the safety guardrails, and drafts the
messages to reach them. One plain-language question, one synthesized answer,
ready to act on.

That's Mission IQ. It reasons across **all** of an organization's information —
structured records, the web, internal docs, and everyday workplace tools — and
turns the answer into action, instead of leaving people to stitch it together
themselves. And the same engine adapts to any mission through interchangeable
**skins** — disaster relief, blood drives, mentoring, and more.

---

## Why this isn't "just a Fabric Data Agent in a chat box"

A lone data agent answers from the one source it owns, read-only. Mission IQ earns
its keep on three axes a single data agent structurally can't:

1. **Cross-source synthesis** — correlates Fabric records + live web + internal
   SOPs + M365 context into a single answer.
2. **Action-taking** — drafts outreach, creates tasks, triggers workflows. Insight
   becomes progress.
3. **Skinnable per mission** — onboard a new mission by filling in a config, not
   rebuilding the tool.

---

## The skin framework

Every mission is the same engine with five pluggable slots:

| Slot | Meaning |
|------|---------|
| **Demand** | The needs to be met, ranked by urgency |
| **Supply** | The constrained resources to allocate |
| **Guardrails** | Eligibility, safety, geography, policy, compliance |
| **Impact** | What "impact per unit resource" means here |
| **Feedback** | Outcomes that re-tune future priorities |

Swapping a skin re-themes the assistant, re-points its data planes, and re-writes
its operating instructions — no orchestration code changes. Ships with three:
🌀 Disaster Relief · 🩸 Blood Drive · 🎓 Youth Mentoring.

---

## Architecture

```
            ┌──────────────────────────────────────────┐
            │   Orchestrator  (gpt-5.4 on Foundry)      │
            │   instructions assembled from the skin    │
            └───────────────┬──────────────────────────┘
        ┌──────────┬────────┼─────────┬──────────────┐
        ▼          ▼        ▼         ▼              ▼
   🗄️ Fabric    🌐 Web   📄 Docs   💼 Work IQ   ⚙️ Actions
   records      live      SOPs /    email /     draft / task /
   (Dynamics)   web       policy    Teams       workflow
        └──────────┴────────┴─────────┴──────────────┘
                            ▼
                  Streamlit "Dispatch Cockpit"
```

- **Orchestrator** — Microsoft Agent Framework on the `gpt-5.4` Foundry
  deployment, Entra ID auth (no keys).
- **Planes** — pluggable tools. The three seeded skins serve realistic local
  mirrors so the app runs anywhere; the **live Fundraising skin** runs on real
  Foundry connectors instead (see below).
- **Actions** — stage outreach/tasks/workflows the human approves in the cockpit.

### The live engine (Fundraising skin)

The Fundraising skin doesn't reason over one big prompt — it runs a **team of
narrow specialists** coordinated by an in-app **Magentic manager**
(`StandardMagenticManager`) that plans, delegates, tracks a progress ledger, and
synthesizes:

| Specialist | Persisted as | Tool (server-side) |
|---|---|---|
| 🗄️ **DonorData** | `MissionIQ-DonorData` | Fabric Data Agent — donor & giving records |
| 📄 **Policy** | `MissionIQ-Policy` | Azure AI Search — SOPs / guardrails |
| 🌐 **Web** | `MissionIQ-Web` | Bing grounding — live external facts |
| ✉️ **Action** | `MissionIQ-Action` | local action tools (draft / task / workflow) |

Each specialist is a **persisted Foundry PromptAgent** (portal-visible) with its
hosted tool lifted into the definition, so it hits the real source. The cockpit
renders the manager's plan, ledger, and every specialist turn in a per-answer
**orchestration drawer**, and lists the live team in the sidebar.

---

## Foundry footprint

Mission IQ provisions real, portal-visible resources into the Foundry project
(`provisioning only — the app itself is run locally`):

- **5 PromptAgents** — the 4 specialists above plus `MissionIQ-Synthesizer`, an
  instructions-only synthesis/action closer.
- **1 Workflow** — `MissionIQ-Workflow`, a declarative CSDL **WorkflowAgentDefinition**
  that consults the team **sequentially over one shared conversation**
  (DonorData → Policy → Web → Synthesizer) and ends with one decision-ready answer
  plus a drafted outreach message. It's the **portal-native twin** of the in-app
  Magentic engine: the app is the dynamic brain; the Workflow is the governed,
  portal-visible orchestration of the *same* persisted agents.

```powershell
# After `az login` to the Foundry tenant:
.\.venv\Scripts\python.exe scripts\provision_foundry_agents.py     # the 4 specialists
.\.venv\Scripts\python.exe scripts\provision_foundry_workflow.py   # synthesizer + workflow
```

Both scripts are **idempotent** (a new version is published only when a definition
changes) and share one source of truth — `agents_spec.py` for the team,
`workflow_spec.py` for the workflow.

---

## Run it

Prerequisites: **Python 3.12**, the Azure CLI signed in (`az login`) to a tenant
with access to the Foundry deployment.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --pre -r requirements.txt
streamlit run app.py
```

Then pick a mission in the sidebar and click a sample question — or ask your own.
See **[`docs/example-questions.md`](docs/example-questions.md)** for demo-ready
prompts (app, Foundry Workflow, and the seeded skins) and a suggested demo arc.

Configuration is optional; copy `.env.example` to `.env` to override the endpoint,
model, or enable live web lookups. To light up the live Fundraising skin's Foundry
agents + workflow, run the two provisioning scripts in **Foundry footprint** above.

---

## Project layout

```
app.py                      Streamlit Dispatch Cockpit (+ team sidebar & Magentic drawer)
src/missioniq/
  config.py                 endpoint / model / api-version + connector settings
  orchestrator.py           builds the Foundry agent + skin instructions (seeded skins)
  live.py                   live-skin engine: tenant-pinned credential + connector planes
  magentic.py               in-app Magentic manager + per-answer trace (plan/ledger/turns)
  agents_spec.py            source of truth for the 4 persisted specialists + manager
  workflow_spec.py          source of truth for the declarative Foundry Workflow (CSDL)
  actions.py                draft_outreach / create_task / trigger_workflow
  planes/                   fabric · fabric_live · web · docs · work (+ base run-context)
  skins/
    schema.py               the 5-slot Skin model + loader
    library/*.yaml          one file per mission skin
scripts/
  provision_foundry_agents.py    publish the 4 specialists as PromptAgents
  provision_foundry_workflow.py  publish MissionIQ-Synthesizer + MissionIQ-Workflow
  build_search_index.py          load the policy/SOP docs into Azure AI Search
data/<skin>/                seed records · web · docs · work per seeded skin
docs/example-questions.md   demo-ready prompts + suggested demo arc
```

## Adding a skin

1. Drop a YAML in `src/missioniq/skins/library/` filling the five slots.
2. Add a `data/<skin_id>/` folder with `records.json`, `web.json`, `docs.json`,
   `work.json`.

No code changes. The new mission shows up in the cockpit automatically.

---

*Demo build. The three seeded skins serve local mirrors so the app runs anywhere;
the live **Fundraising** skin runs on real Foundry connectors and a persisted
specialist team. Provisioning publishes agents + a workflow to the project — the
app itself is run locally, not deployed.*
