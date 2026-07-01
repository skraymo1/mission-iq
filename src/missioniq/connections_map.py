"""Architecture-map builder — the DOT for the cockpit's "how it's connected" screen.

Pure (no Streamlit) so the app can render it with `st.graphviz_chart` and tests can
assert on it. Given a skin + its effective settings, it draws the operator question →
manager → each specialist → its real backend (Fabric Data Agent / AI Search index /
curated web snapshot / action tools), colour-coded LIVE vs curated vs client-side.
"""
from __future__ import annotations

from .agents_spec import MANAGER_NAME, active_team
from .config import Settings
from .skins.schema import Skin

# Palette
_LIVE = ("#dcfce7", "#065f46")     # green — live connector
_HYBRID = ("#fef3c7", "#92400e")   # amber — curated / seeded
_CLIENT = ("#dbeafe", "#1e40af")   # blue  — client-side action tools


def backend_for(spec, skin: Skin, eff: Settings) -> dict:
    """Describe the data/action backend a specialist is wired to, for the map."""
    conn = eff.fabric_connection_id.split("/")[-1]
    if spec.key in ("DonorData", "FieldStaff"):
        warehouse = ("fieldresponse_demo warehouse" if skin.id == "field_response"
                     else "gold fundraising model")
        return {"label": f"🗄️ Fabric Data Agent\\n{conn}\\n→ {warehouse}",
                "fill": _LIVE[0], "fc": _LIVE[1], "shape": "cylinder", "edge": "LIVE"}
    if spec.key == "Policy":
        return {"label": f"📄 Azure AI Search\\n{eff.search_index_name}",
                "fill": _LIVE[0], "fc": _LIVE[1], "shape": "cylinder", "edge": "LIVE"}
    if spec.key == "Web":
        if skin.id == "field_response":
            return {"label": "🌐 Curated situation snapshot\\n(web.json)",
                    "fill": _HYBRID[0], "fc": _HYBRID[1], "shape": "note",
                    "edge": "HYBRID"}
        return {"label": "🌐 Bing grounding\\n(live external web)",
                "fill": _LIVE[0], "fc": _LIVE[1], "shape": "box", "edge": "LIVE"}
    return {"label": "✉️ Action tools\\ndraft · task · workflow",
            "fill": _CLIENT[0], "fc": _CLIENT[1], "shape": "component",
            "edge": "stages for approval"}


def build_connections_dot(skin: Skin, eff: Settings) -> str:
    """Graphviz DOT for the skin's live (or seeded) architecture."""
    L = [
        "digraph G {",
        'rankdir=LR; bgcolor="transparent"; nodesep=0.35; ranksep=0.7;',
        'node [fontname="Segoe UI", fontsize=11, style="filled,rounded", '
        'shape=box, color="#cbd5e1", fontcolor="#0f172a"];',
        'edge [color="#94a3b8", arrowsize=0.7, fontname="Segoe UI"];',
        'q [label="🗣️ Operator question", fillcolor="#e2e8f0"];',
    ]
    if skin.live:
        L.append(f'mgr [label="🧠 {MANAGER_NAME}\\n(gpt-5.4 · Magentic manager)", '
                 f'fillcolor="{skin.accent}", fontcolor="white", color="{skin.accent}"];')
        L.append("q -> mgr;")
        for spec in active_team(eff, skin.id):
            nid = spec.key.lower()
            L.append(f'{nid} [label="{spec.icon} {spec.persisted_name}\\n{spec.detail}", '
                     f'fillcolor="#f8fafc"];')
            L.append(f"mgr -> {nid} [dir=both];")
            b = backend_for(spec, skin, eff)
            L.append(f'{nid}_b [label="{b["label"]}", fillcolor="{b["fill"]}", '
                     f'fontcolor="{b["fc"]}", shape={b["shape"]}, color="{b["fill"]}"];')
            L.append(f'{nid} -> {nid}_b [label="{b["edge"]}", fontsize=9, '
                     f'fontcolor="#64748b"];')
    else:
        L.append(f'ag [label="🧭 MissionIQ\\n(gpt-5.4)", fillcolor="{skin.accent}", '
                 f'fontcolor="white", color="{skin.accent}"];')
        L.append("q -> ag;")
        planes = [
            ("fab", "🗄️ Fabric records", "records.json"),
            ("web", "🌐 Web conditions", "web.json"),
            ("doc", "📄 Docs · SOPs", "docs.json"),
            ("wiq", "💼 Work IQ", "work.json"),
        ]
        for nid, label, fname in planes:
            L.append(f'{nid} [label="{label}", fillcolor="#f8fafc"];')
            L.append(f"ag -> {nid} [dir=both];")
            L.append(f'{nid}_b [label="data/{skin.id}/{fname}", fillcolor="{_HYBRID[0]}", '
                     f'fontcolor="{_HYBRID[1]}", shape=note, color="{_HYBRID[0]}"];')
            L.append(f'{nid} -> {nid}_b [label="seeded", fontsize=9, fontcolor="#64748b"];')
    L.append("}")
    return "\n".join(L)
