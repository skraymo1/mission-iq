"""One-off: build the Mission IQ fundraising docs index in Azure AI Search.

Reads data/fundraising/docs.json and uploads each document into a keyword+semantic
index that the Foundry Azure AI Search connector (docs plane) will query.
"""
import json
import os
import pathlib
import httpx

ENDPOINT = "https://aisearchiux0jeg.search.windows.net"
INDEX = "missioniq-fundraising-docs"
API = "2024-07-01"
KEY = pathlib.Path(os.environ["TEMP"], "_aiskey.txt").read_text().strip()
H = {"Content-Type": "application/json", "api-key": KEY}

index_def = {
    "name": INDEX,
    "fields": [
        {"name": "id", "type": "Edm.String", "key": True, "filterable": True},
        {"name": "title", "type": "Edm.String", "searchable": True, "retrievable": True},
        {"name": "content", "type": "Edm.String", "searchable": True, "retrievable": True},
        {"name": "source", "type": "Edm.String", "searchable": True, "retrievable": True, "filterable": True},
    ],
    "semantic": {
        "configurations": [
            {
                "name": "default",
                "prioritizedFields": {
                    "titleField": {"fieldName": "title"},
                    "prioritizedContentFields": [{"fieldName": "content"}],
                    "prioritizedKeywordsFields": [{"fieldName": "source"}],
                },
            }
        ]
    },
}

with httpx.Client(timeout=30) as c:
    # (re)create index
    c.delete(f"{ENDPOINT}/indexes/{INDEX}?api-version={API}", headers=H)
    r = c.put(f"{ENDPOINT}/indexes/{INDEX}?api-version={API}", headers=H, json=index_def)
    print("create index:", r.status_code, r.text[:200])
    r.raise_for_status()

    docs = json.loads(pathlib.Path("data/fundraising/docs.json").read_text(encoding="utf-8"))
    source = docs["source"]
    actions = [
        {
            "@search.action": "mergeOrUpload",
            "id": str(i),
            "title": d["title"],
            "content": d["snippet"],
            "source": source,
        }
        for i, d in enumerate(docs["documents"])
    ]
    r = c.post(
        f"{ENDPOINT}/indexes/{INDEX}/docs/index?api-version={API}",
        headers=H,
        json={"value": actions},
    )
    print("upload:", r.status_code, r.text[:300])
    r.raise_for_status()

print(f"OK — indexed {len(actions)} docs into {INDEX}")
