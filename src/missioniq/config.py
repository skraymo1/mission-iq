"""Runtime configuration for Mission IQ.

All values can be overridden via environment variables (optionally loaded from a
local .env file). Defaults point at the verified Foundry resource so the app runs
out of the box against the real gpt-5.4 deployment.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv optional
    pass


@dataclass(frozen=True)
class Settings:
    """Connection settings for the Foundry-hosted model."""

    endpoint: str
    model: str
    api_version: str

    # Foundry project + live connectors (used by the "live" skins).
    project_endpoint: str
    fabric_connection_id: str
    bing_connection_id: str
    search_connection_id: str
    search_index_name: str

    # Entra tenant that owns the Foundry resource. Pinning the credential to this
    # tenant keeps multi-account dev boxes from authenticating as the wrong
    # identity (DefaultAzureCredential otherwise picks up a cached/VS identity in
    # a different tenant, which Foundry then rejects with a 403).
    tenant_id: str = ""

    @property
    def display_endpoint(self) -> str:
        return self.endpoint.replace("https://", "").rstrip("/")

    @property
    def has_fabric(self) -> bool:
        return bool(self.fabric_connection_id)


# Full ARM connection-id base for the missionIQ project's connections.
_CONN_BASE = (
    "/subscriptions/cc454204-b93e-4edf-851a-29c447577cd9/resourceGroups/rg-ffdemo"
    "/providers/Microsoft.CognitiveServices/accounts/missioniq-resource"
    "/projects/missioniq/connections"
)


def load_settings() -> Settings:
    return Settings(
        endpoint=os.getenv(
            "MISSIONIQ_FOUNDRY_ENDPOINT",
            "https://missioniq-resource.cognitiveservices.azure.com/",
        ),
        model=os.getenv("MISSIONIQ_MODEL", "gpt-5.4"),
        # The /openai/v1 surface used by Agent Framework expects "preview".
        api_version=os.getenv("MISSIONIQ_API_VERSION", "preview"),
        project_endpoint=os.getenv(
            "MISSIONIQ_PROJECT_ENDPOINT",
            "https://missioniq-resource.services.ai.azure.com/api/projects/missionIQ",
        ),
        # Fabric Data Agent connection — published & wired (CustomKeys connection
        # holding workspace-id/artifact-id; auth is identity-passthrough/OBO).
        fabric_connection_id=os.getenv(
            "MISSIONIQ_FABRIC_CONNECTION_ID", f"{_CONN_BASE}/missioniq-fabric"
        ),
        bing_connection_id=os.getenv(
            "MISSIONIQ_BING_CONNECTION_ID", f"{_CONN_BASE}/missioniq-bing"
        ),
        search_connection_id=os.getenv(
            "MISSIONIQ_SEARCH_CONNECTION_ID", f"{_CONN_BASE}/missioniq-search"
        ),
        search_index_name=os.getenv(
            "MISSIONIQ_SEARCH_INDEX", "missioniq-fundraising-docs"
        ),
        tenant_id=os.getenv(
            "MISSIONIQ_TENANT_ID", "d97e8bab-6e30-49cc-9d1d-d1a4cd148170"
        ),
    )


# Toggle a real outbound web call in the web plane. Off by default so demos are
# deterministic and offline-safe; flip to "1" to attempt live lookups.
LIVE_WEB = os.getenv("MISSIONIQ_LIVE_WEB", "0") == "1"
