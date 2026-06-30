"""Shared plumbing for planes and actions.

A *plane* is a data source the orchestrator can consult (Fabric records, the web,
internal docs, the M365 workplace). An *action* is something it can do (draft
outreach, create a task, trigger a workflow).

Every tool is bound to a `RunContext` so the UI can show, after each turn, which
planes were consulted and which actions were proposed — the cross-source +
action story made visible.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parents[3] / "data"


@dataclass
class SourceTouch:
    plane: str
    icon: str
    detail: str


@dataclass
class ProposedAction:
    kind: str
    icon: str
    title: str
    body: str


@dataclass
class AgentTurn:
    """One specialist's contribution during a Magentic run, for the cockpit."""

    name: str
    icon: str
    text: str


@dataclass
class MagenticTrace:
    """The manager's plan + progress ledger + per-specialist turns for one run."""

    plan: str = ""
    ledger: list[str] = field(default_factory=list)
    turns: list[AgentTurn] = field(default_factory=list)
    rounds: int = 0
    replans: int = 0


@dataclass
class RunContext:
    """Collects what happened during a single question, for UI attribution."""

    sources: list[SourceTouch] = field(default_factory=list)
    actions: list[ProposedAction] = field(default_factory=list)
    # Populated only on live (Magentic) turns — the orchestration trace.
    magentic: MagenticTrace | None = None

    def touch(self, plane: str, icon: str, detail: str) -> None:
        self.sources.append(SourceTouch(plane=plane, icon=icon, detail=detail))

    def propose(self, kind: str, icon: str, title: str, body: str) -> None:
        self.actions.append(ProposedAction(kind=kind, icon=icon, title=title, body=body))


def load_data(skin_id: str, name: str) -> dict[str, Any]:
    """Load a seed JSON file for a skin, e.g. load_data('disaster_relief', 'records')."""
    path = DATA_DIR / skin_id / f"{name}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _stringify(record: dict[str, Any]) -> str:
    parts: list[str] = []
    for value in record.values():
        if isinstance(value, list):
            parts.extend(str(v) for v in value)
        else:
            parts.append(str(value))
    return " ".join(parts).lower()


def score_records(
    records: list[dict[str, Any]], query: str, top: int = 6
) -> list[dict[str, Any]]:
    """Tiny keyword matcher standing in for a real DAX/SQL filter.

    Scores each record by how many query tokens appear anywhere in its fields,
    lightly boosting availability/eligibility and reliability so the most useful
    rows surface first. Good enough to make the demo feel real; the real Fabric
    plane swaps this for an executeQueries DAX call.
    """
    tokens = [t for t in "".join(c if c.isalnum() else " " for c in query.lower()).split() if len(t) > 2]
    scored: list[tuple[float, dict[str, Any]]] = []
    for rec in records:
        blob = _stringify(rec)
        score = sum(1.0 for t in tokens if t in blob)
        if rec.get("available_tonight") or rec.get("eligible") or rec.get("cleared"):
            score += 0.5
        score += float(rec.get("reliability", 0)) * 0.3
        scored.append((score, rec))
    scored.sort(key=lambda x: x[0], reverse=True)
    ranked = [rec for s, rec in scored if s > 0] or [rec for _, rec in scored]
    return ranked[:top]
