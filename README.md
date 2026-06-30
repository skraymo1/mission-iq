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

- **Orchestrator** — Microsoft Agent Framework agent on the `gpt-5.4` Foundry
  deployment, Entra ID auth (no keys).
- **Planes** — pluggable tools. Today each serves a realistic seeded mirror with a
  clean swap point to go live (Fabric `executeQueries` DAX / Foundry native
  `get_fabric_tool`, Bing grounding, file-search RAG, Work IQ / Graph).
- **Actions** — stage outreach/tasks/workflows the human approves in the cockpit.

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

Configuration is optional; copy `.env.example` to `.env` to override the endpoint,
model, or enable live web lookups.

---

## Project layout

```
app.py                      Streamlit Dispatch Cockpit
src/missioniq/
  config.py                 endpoint / model / api-version settings
  orchestrator.py           builds the Foundry agent + skin instructions
  actions.py                draft_outreach / create_task / trigger_workflow
  planes/                   fabric · web · docs · work (+ base run-context)
  skins/
    schema.py               the 5-slot Skin model + loader
    library/*.yaml          one file per mission skin
data/<skin>/                seed records · web · docs · work per skin
```

## Adding a skin

1. Drop a YAML in `src/missioniq/skins/library/` filling the five slots.
2. Add a `data/<skin_id>/` folder with `records.json`, `web.json`, `docs.json`,
   `work.json`.

No code changes. The new mission shows up in the cockpit automatically.

---

*Demo build. Data planes serve seeded mirrors by design so the app runs anywhere;
each has a documented swap to its live Azure source.*
