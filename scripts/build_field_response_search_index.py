r"""One-off: build the Mission IQ **Field Response** deployment-SOP index in Azure AI Search.

Reads data/field_response/docs.json and uploads each document into a keyword+semantic
index that the Field Response Policy specialist (Azure AI Search connector) queries.

Mirrors scripts/build_search_index.py (fundraising) but targets the field-response
index name and data file, so the two missions ground on independent doc sets.

    $env:PYTHONIOENCODING="utf-8"; $env:PYTHONUTF8="1"
    .\.venv\Scripts\python.exe scripts\build_field_response_search_index.py
"""
import json
import os
import pathlib
import httpx

ENDPOINT = "https://aisearchiux0jeg.search.windows.net"
INDEX = "missioniq-fieldresponse-docs"
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

    docs = json.loads(pathlib.Path("data/field_response/docs.json").read_text(encoding="utf-8"))
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
