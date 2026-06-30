# Mission IQ — Example Questions

Demo-ready prompts, organized by **where** you ask them. The flagship is the
**live Fundraising skin**, which reasons over real Foundry connectors — Fabric
(donor records), Azure AI Search (policy/SOPs), and Bing (live web) — and stages
real actions.

> Tip for the room: every flagship question is built to light up **all three**
> differentiators — cross-source synthesis, live data, and an action — in one shot.

---

## 1) In the app — live Fundraising skin (Magentic cockpit)

Ask these in the Streamlit cockpit with the **💝 Fundraising** skin selected. The
in-app **Magentic manager** plans, delegates to the specialists, and synthesizes —
watch the **orchestration drawer** under each answer to see the plan, the progress
ledger, and each specialist's turn.

| Question | What it exercises |
|---|---|
| **"Which lapsed major donors should we reach before year-end, and is it okay to ask them?"** | 🗄️ DonorData (Fabric: lapsed + capacity) → 📄 Policy (do-not-solicit / cadence) → 🌐 Web (year-end deadline) → ⚙️ Action (drafts the asks). The full cross-source + action story. |
| **"Who are our top untapped high-capacity prospects this quarter, and what's the right first move?"** | DonorData ranks capacity/recency; Policy checks first-contact rules; Action stages an intro task per prospect. |
| **"Draft a personal year-end ask to our best lapsed donor — and flag anything compliance should see first."** | DonorData picks the donor with real giving history; Policy surfaces guardrails; Action drafts the message with "pending CRM clearance" if needed. |
| **"A donor's company was just in the news — should we adjust our ask, and how?"** | 🌐 Web leads (live news), DonorData supplies the relationship/history, Policy checks gift-acceptance, Action revises the outreach. Shows Web as the driver. |

**Single-plane probes** (use to show one connector cleanly, or to debug):

- *"What's the lifetime giving and last gift for our top 5 donors by capacity?"* → DonorData / Fabric only.
- *"What does our gift acceptance policy say about anonymous major gifts?"* → Policy / AI Search only.
- *"What's the IRS deadline for year-end charitable deductions this year?"* → Web / Bing only.

---

## 2) In Foundry — the declarative Workflow (`MissionIQ-Workflow`)

Run these from the **Foundry portal playground** (Workflows → MissionIQ-Workflow →
Try) or the VS Code remote playground. The workflow consults the team **in
sequence over one shared conversation** — 🗄️ DonorData → 📄 Policy → 🌐 Web → 🧭
Synthesizer — so you'll see each specialist's contribution stream in, then one
decision-ready answer with a drafted outreach message at the end.

- **"Which lapsed major donors should we reach before year-end, and draft the outreach for the top one."**
- **"Recommend who to ask for a year-end gift, reconcile it against our do-not-solicit and anonymity rules, and write the message."**
- **"Build me a prioritized year-end ask list with the real donor names and figures, then draft the top outreach."**

> Why these work well here: the closer (`MissionIQ-Synthesizer`) is built to fold
> every specialist's findings into a single recommendation **plus** an inline
> drafted message — so a one-line prompt yields a complete, skimmable answer.

---

## 3) The seeded skins (offline-safe — no live connectors)

These run anywhere on built-in demo data, ideal when you want to show the
**skinnable** story without touching Azure. Switch skins in the sidebar.

**🌀 Disaster Relief**
- "Who can I get to the Houston shelter tonight?"
- "There's a medical surge in Zone 4 — who's certified and closest?"
- "Draft an urgent callout to available drivers for tomorrow's supply run."

**🩸 Blood Drive**
- "We're 12 O-negative units short for tomorrow — who do we call?"
- "Which lapsed donors near downtown are eligible again this week?"
- "Draft a reminder text to everyone booked for Saturday's drive."

**🎓 Youth Mentoring**
- "Which students are slipping and who's the right mentor for each?"
- "Find an available Spanish-speaking math mentor near the east campus."
- "Draft an intro message pairing Mr. Allen with the three flagged students."

---

## Suggested demo arc (≈5 min)

1. **Open on the seeded Disaster Relief skin** — ask *"Who can I get to the Houston
   shelter tonight?"* to land the scenario and the cross-source + action feel.
2. **Switch to 💝 Fundraising (live)** — ask the year-end lapsed-donor question and
   open the **orchestration drawer** to reveal the Magentic plan + real specialist
   turns hitting Fabric / Search / Bing.
3. **Cut to the Foundry portal** — run the same question through
   **MissionIQ-Workflow** to show the **portal-native** declarative twin of the
   same agents. "The app is the dynamic brain; this is the governed, portal-visible
   orchestration of the very same specialists."
