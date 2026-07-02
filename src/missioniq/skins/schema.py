"""The Skin system — the heart of Mission IQ's "build once, re-skin per mission" idea.

Every mission (disaster relief, blood drive, mentoring, ...) is the same engine
with five pluggable slots filled in:

    1. Demand     — the needs to be met, ranked by urgency
    2. Supply     — the constrained resources to allocate
    3. Guardrails — eligibility, safety, geography, policy, compliance rules
    4. Impact     — what "impact per unit resource" means for this mission
    5. Feedback   — outcomes that re-tune future priorities

A Skin is pure configuration (YAML). Swapping skins re-themes the assistant,
re-points its data planes, and re-writes its operating instructions — without
touching a line of orchestration code.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

LIBRARY_DIR = Path(__file__).parent / "library"


@dataclass(frozen=True)
class Skin:
    id: str
    name: str
    icon: str
    accent: str
    tagline: str
    entity: str  # the primary record type, e.g. "volunteers", "donors"

    # The five pluggable slots.
    demand: str
    supply: str
    guardrails: str
    impact: str
    feedback: str

    sample_questions: list[str] = field(default_factory=list)

    # When true, this skin's planes are backed by live Foundry connectors
    # (Fabric Data Agent, Bing grounding, Azure AI Search) instead of seed JSON.
    live: bool = False

    @property
    def slots(self) -> list[tuple[str, str, str]]:
        """(label, emoji, value) for each of the five framework slots."""
        return [
            ("Demand", "📍", self.demand),
            ("Supply", "🧰", self.supply),
            ("Guardrails", "🛡️", self.guardrails),
            ("Impact", "🎯", self.impact),
            ("Feedback", "🔁", self.feedback),
        ]


def _from_dict(data: dict[str, Any]) -> Skin:
    return Skin(
        id=data["id"],
        name=data["name"],
        icon=data.get("icon", "🧭"),
        accent=data.get("accent", "#2563eb"),
        tagline=data["tagline"],
        entity=data["entity"],
        demand=data["demand"],
        supply=data["supply"],
        guardrails=data["guardrails"],
        impact=data["impact"],
        feedback=data["feedback"],
        sample_questions=data.get("sample_questions", []),
        live=bool(data.get("live", False)),
    )


def load_skins() -> dict[str, Skin]:
    """Load every skin in the library, keyed by id, ordered by filename."""
    skins: dict[str, Skin] = {}
    for path in sorted(LIBRARY_DIR.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        skin = _from_dict(data)
        skins[skin.id] = skin
    return skins
