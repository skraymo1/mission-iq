"""Fabric plane — structured records (the Dynamics → Fabric system of record).

Today this serves a seeded mirror and matches with a tiny keyword scorer. The
go-live swap is a single function body: call the Fabric / Power BI
`executeQueries` DAX endpoint (or the Foundry native `get_fabric_tool`) and
return rows. Everything above this layer stays identical.
"""
import json
from typing import Annotated, Callable

from pydantic import Field

from ..skins.schema import Skin
from .base import RunContext, load_data, score_records


def make_fabric_tool(skin: Skin, ctx: RunContext) -> Callable[..., str]:
    data = load_data(skin.id, "records")
    records = data.get("records", [])
    needs = data.get("needs", [])
    entity = skin.entity

    def query_records(
        filter: Annotated[
            str,
            Field(description=f"Natural-language filter to find {entity}, e.g. skills/type, location, and availability."),
        ],
    ) -> str:
        ctx.touch("Fabric", "🗄️", f"queried {entity} · '{filter}'")
        matches = score_records(records, filter)
        payload = {
            "entity": entity,
            "open_needs": needs,
            "matches": matches,
        }
        return json.dumps(payload, indent=2)

    query_records.__name__ = f"query_{entity}"
    query_records.__doc__ = (
        f"Query the organization's structured {entity} records (Dynamics → Fabric) "
        f"and the current open needs. Returns matching {entity} with their key "
        f"attributes plus the active demand list. Use this for any question about "
        f"who/what is available and what the current needs are."
    )
    return query_records
