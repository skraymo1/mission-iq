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
from missioniq.config import load_settings  # noqa: E402
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
        st.markdown("**🟢 LIVE — real Foundry connectors**")
        for p in connector_planes(settings):
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
        for spec in active_team(settings):
            st.caption(
                f"{spec.icon} **{spec.persisted_name}** — {spec.detail}  ·  "
                "_persisted in Foundry_"
            )
    else:
        st.caption("Planes: 🗄️ Fabric · 🌐 Web · 📄 Docs · 💼 Work IQ  ·  _seeded demo_")


# ------------------------------------------------------------ chat state
# Keep a separate transcript per skin so switching missions is a clean slate.
store = st.session_state.setdefault("transcripts", {})
messages = store.setdefault(skin_id, [])

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
