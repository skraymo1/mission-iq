"""Mission IQ — Dispatch Cockpit (Streamlit).

Pick a mission skin, ask in plain language, and watch the assistant reason across
planes (Fabric · Web · Docs · Work IQ) and stage real actions.

Run:  streamlit run app.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "src"))

from missioniq.agents_spec import MANAGER_NAME, active_team  # noqa: E402
from missioniq.config import load_settings, settings_for_skin  # noqa: E402
from missioniq.connections_map import build_connections_dot  # noqa: E402
from missioniq.live import connector_planes  # noqa: E402
from missioniq.orchestrator import Clients, run_turn  # noqa: E402
from missioniq.planes import RunContext  # noqa: E402
from missioniq.skins import load_skins  # noqa: E402

st.set_page_config(page_title="Mission IQ", page_icon="🧭", layout="wide")


@st.cache_resource(show_spinner=False)
def _settings():
    return load_settings()


@st.cache_resource(show_spinner=False)
def _clients():
    return Clients(_settings())


@st.cache_resource(show_spinner=False)
def _skins():
    return load_skins()


settings = _settings()
skins = _skins()


# ---------------------------------------------- connection-map (architecture)
def render_connections(skin, settings) -> None:
    """The 'how it's connected' screen — a live architecture map for the audience."""
    eff = settings_for_skin(settings, skin.id)
    st.markdown(f"### 🔌 How {skin.name} is connected")
    if skin.live:
        st.caption(
            "Each specialist owns exactly one connector. The manager (gpt-5.4) plans, "
            "delegates, and synthesizes across them — the Magentic pattern over real "
            "Foundry-persisted agents."
        )
    else:
        st.caption(
            "This mission runs on the seeded plane path — one agent over local demo "
            "data, so it runs anywhere with no provisioning. Flip it live to swap "
            "these files for real Foundry connectors."
        )

    st.graphviz_chart(build_connections_dot(skin, eff), use_container_width=True)

    # Legend
    st.markdown(
        "<span style='background:#dcfce7;color:#065f46;padding:2px 8px;border-radius:6px'>"
        "🟢 LIVE connector</span> &nbsp; "
        "<span style='background:#fef3c7;color:#92400e;padding:2px 8px;border-radius:6px'>"
        "🟡 curated / seeded</span> &nbsp; "
        "<span style='background:#dbeafe;color:#1e40af;padding:2px 8px;border-radius:6px'>"
        "🔵 client-side action</span>",
        unsafe_allow_html=True,
    )

    if skin.live:
        st.divider()
        st.markdown("**Wired resources**")
        st.caption(f"🧠 Model · `{settings.model}` @ `{settings.display_endpoint}`")
        st.caption(f"🗄️ Fabric connection · `{eff.fabric_connection_id.split('/')[-1]}`")
        st.caption(f"📄 Search index · `{eff.search_index_name}`")
        if skin.id == "field_response":
            st.caption(
                "🌐 Web · **curated situation snapshot** (hybrid) — the field sitrep is "
                "pinned so the outbreak / border-closure override is deterministic on "
                "stage; Fabric + Docs are fully live."
            )
        else:
            st.caption("🌐 Web · `Bing grounding` (live)")
        team = active_team(eff, skin.id)
        roster = " · ".join(f"{s.icon} {s.persisted_name}" for s in team)
        st.caption(f"🤝 Team · {MANAGER_NAME} → {roster}")


# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.markdown("## 🧭 Mission IQ")
    st.caption("One assistant. Every mission. Reasons across your data — and acts.")

    skin_id = st.radio(
        "Mission skin",
        options=list(skins.keys()),
        format_func=lambda k: f"{skins[k].icon}  {skins[k].name}",
        key="skin_id",
    )
    skin = skins[skin_id]

    st.markdown(f"**{skin.icon} {skin.name}**")
    st.caption(skin.tagline)

    with st.expander("The five slots this skin fills", expanded=False):
        for label, emoji, value in skin.slots:
            st.markdown(f"{emoji} **{label}** — {value.strip()}")

    st.divider()
    st.caption(f"🧠 {settings.model}  ·  {settings.display_endpoint}")
    if skin.live:
        eff = settings_for_skin(settings, skin.id)
        st.markdown("**🟢 LIVE — real Foundry connectors**")
        for p in connector_planes(eff, skin):
            wired = p["wired"] == "True"
            mark = "🟢" if wired else "⚪"
            note = "" if wired else "  _(not connected)_"
            st.caption(f"{mark} {p['icon']} **{p['label']}** — {p['detail']}{note}")

        st.divider()
        st.markdown("**🤝 Specialist team**")
        st.caption(
            "A manager orchestrates four narrow specialists (Magentic pattern) — "
            "each owns exactly one connector."
        )
        st.caption(f"🧠 **{MANAGER_NAME}** — orchestrates the team  ·  _in-app_")
        for spec in active_team(eff, skin.id):
            persisted = (
                "_client-side_"
                if (spec.local_action_tools or spec.local_web_snapshot)
                else "_persisted in Foundry_"
            )
            st.caption(
                f"{spec.icon} **{spec.persisted_name}** — {spec.detail}  ·  {persisted}"
            )
    else:
        st.caption("Planes: 🗄️ Fabric · 🌐 Web · 📄 Docs · 💼 Work IQ  ·  _seeded demo_")


# ------------------------------------------------------------ chat state
# Keep a separate transcript per skin so switching missions is a clean slate.
store = st.session_state.setdefault("transcripts", {})
messages = store.setdefault(skin_id, [])

view = st.radio(
    "View",
    ["🛰️ Cockpit", "🔌 Connections"],
    horizontal=True,
    label_visibility="collapsed",
    key=f"view_{skin_id}",
)

if view == "🔌 Connections":
    render_connections(skin, settings)
    st.stop()

st.markdown(f"### {skin.icon} {skin.name} — Cockpit")
st.caption(skin.tagline)

# Sample-question chips
cols = st.columns(len(skin.sample_questions))
pending = st.session_state.pop("pending_question", None)
for i, q in enumerate(skin.sample_questions):
    if cols[i].button(q, key=f"sample_{skin_id}_{i}", use_container_width=True):
        pending = q


def _render_magentic(trace) -> None:
    """Render the manager's plan, progress ledger, and per-specialist turns."""
    if not trace or not (trace.plan or trace.ledger or trace.turns):
        return

    n = len(trace.turns)
    bits = [f"{n} specialist {'turn' if n == 1 else 'turns'}"]
    if trace.rounds:
        bits.append(f"{trace.rounds} rounds")
    if trace.replans:
        bits.append(f"{trace.replans} replan{'' if trace.replans == 1 else 's'}")
    header = "🧠 How the team reasoned — " + " · ".join(bits)

    with st.expander(header, expanded=False):
        if trace.plan:
            st.markdown("**📋 Manager's plan**")
            st.markdown(trace.plan)
        if trace.ledger:
            st.markdown("**🧭 Progress ledger**")
            for step in trace.ledger:
                st.markdown(f"- {step}")
        if trace.turns:
            st.markdown("**🗣️ Specialist turns**")
            for turn in trace.turns:
                with st.container(border=True):
                    st.markdown(f"**{turn.icon} {turn.name}**")
                    st.markdown(turn.text)


def _render_message(msg: dict) -> None:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("sources"):
            chips = "  ".join(f"`{s.icon} {s.plane}`" for s in msg["sources"])
            st.caption(f"Sources consulted: {chips}")
        for action in msg.get("actions", []):
            with st.container(border=True):
                st.markdown(f"**{action.icon} {action.title}**")
                st.markdown(action.body)
                st.button("Approve & send", key=f"approve_{id(action)}", type="primary")
        _render_magentic(msg.get("magentic"))


for msg in messages:
    _render_message(msg)


def _answer(question: str) -> None:
    messages.append({"role": "user", "content": question})
    _render_message(messages[-1])

    ctx = RunContext()
    spin = (
        "Reasoning across 🗄️ Fabric · 📄 AI Search · 🌐 Bing — live…"
        if skin.live
        else "Reasoning across Fabric · Web · Docs · Work IQ…"
    )
    with st.chat_message("assistant"):
        with st.spinner(spin):
            try:
                text = asyncio.run(run_turn(skin, ctx, settings, _clients(), question))
            except Exception as exc:  # surface auth/config errors clearly
                text = f"⚠️ Could not complete the request: `{exc}`"
    messages.append(
        {
            "role": "assistant",
            "content": text,
            "sources": ctx.sources,
            "actions": ctx.actions,
            "magentic": ctx.magentic,
        }
    )
    st.rerun()


typed = st.chat_input(f"Ask about {skin.name.lower()}…")
question = typed or pending
if question:
    _answer(question)
