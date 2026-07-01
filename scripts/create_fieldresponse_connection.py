r"""Create the Foundry **Fabric Data Agent** connection for the Field Response skin.

This mirrors the fundraising connection (`missioniq-fabric`) exactly — a CustomKeys
connection whose `target` points at the published Fabric Data Agent (AI Skill) and
whose metadata marks it `ApiType: Fabric`. The Field Response Fabric specialist
(`MissionIQ-FieldStaff`) resolves this connection via
`config.settings_for_skin(..., "field_response")`.

Prereq: you have created + PUBLISHED the Field Response Data Agent in the Fabric
workspace and copied its artifact GUID from the URL (.../aiskills/<GUID>).

    $env:PYTHONIOENCODING="utf-8"; $env:PYTHONUTF8="1"
    .\.venv\Scripts\python.exe scripts\create_fieldresponse_connection.py <ARTIFACT_GUID>

Auth: uses `az account get-access-token` for ARM, so `az login` must be the Foundry
tenant identity (admin@MngEnvMCAP727505.onmicrosoft.com).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SUBSCRIPTION = "cc454204-b93e-4edf-851a-29c447577cd9"
RESOURCE_GROUP = "rg-ffdemo"
ACCOUNT = "missioniq-resource"
PROJECT = "missioniq"
CONNECTION = "missioniq-fieldresponse-fabric"
WORKSPACE_ID = "b755437b-5db7-4f98-8a8f-8539e5bf503b"
API_VERSION = "2025-04-01-preview"


def _arm_url() -> str:
    return (
        f"https://management.azure.com/subscriptions/{SUBSCRIPTION}"
        f"/resourceGroups/{RESOURCE_GROUP}/providers/Microsoft.CognitiveServices"
        f"/accounts/{ACCOUNT}/projects/{PROJECT}/connections/{CONNECTION}"
        f"?api-version={API_VERSION}"
    )


def _body(artifact_id: str) -> dict:
    target = (
        f"https://fabric.microsoft.com/groups/{WORKSPACE_ID}"
        f"/aiskills/{artifact_id}"
    )
    return {
        "properties": {
            "authType": "CustomKeys",
            "category": "CustomKeys",
            "target": target,
            "isSharedToAll": False,
            "metadata": {"ApiType": "Fabric"},
            "credentials": {
                "keys": {
                    "workspace-id": WORKSPACE_ID,
                    "artifact-id": artifact_id,
                }
            },
        }
    }


def _az_rest(method: str, url: str, body: dict | None = None) -> str:
    cmd = ["az", "rest", "--method", method, "--url", url]
    tmp: Path | None = None
    if body is not None:
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)  # Windows locks the fd; close before az reads the file
        tmp = Path(path)
        tmp.write_text(json.dumps(body), encoding="utf-8")
        cmd += ["--body", f"@{tmp}",
                "--headers", "Content-Type=application/json"]
    try:
        out = subprocess.run(
            cmd, capture_output=True, text=True, shell=True
        )
    finally:
        if tmp is not None:
            try:
                tmp.unlink()
            except OSError:
                pass
    if out.returncode != 0:
        raise SystemExit(f"az rest {method} failed:\n{out.stderr or out.stdout}")
    return out.stdout


def main() -> int:
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        raise SystemExit(
            "Usage: create_fieldresponse_connection.py <ARTIFACT_GUID>\n"
            "  (the published Field Response Data Agent id from its Fabric URL)"
        )
    artifact_id = sys.argv[1].strip()
    url = _arm_url()

    print(f"Creating connection {CONNECTION}")
    print(f"  → target aiskills/{artifact_id}\n")
    result = _az_rest("put", url, _body(artifact_id))
    data = json.loads(result) if result.strip() else {}
    props = data.get("properties", {})
    print("Created:")
    print(f"  name    : {data.get('name')}")
    print(f"  authType: {props.get('authType')}")
    print(f"  apiType : {props.get('metadata', {}).get('ApiType')}")
    print(f"  target  : {props.get('target')}")
    print("\nField Response Fabric plane is now wired. Next: persist the team")
    print("  ($env:MISSIONIQ_TEAM='field_response'; "
          "python scripts\\provision_foundry_agents.py) and flip the skin live.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
