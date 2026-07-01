"""Load the Field Response gold star schema into a dedicated Fabric warehouse.

This is the **go-live artifact** for the Field Response skin's Fabric plane. It is
inert until you run it: nothing here touches Azure at import time.

Design (Option 1 — a *separate* warehouse per mission, so a second Fabric Data
Agent can be scoped to only these tables and the donor tables never pollute its
grounding):

    dbo.dm_FieldStaff          -- the roster (analog of dm_Constituent)
    dbo.dm_Country             -- reference: region + static baseline risk tier
    dbo.FactStaffLanguage      -- staff <-> language (match guardrail)
    dbo.FactStaffVaccination   -- staff <-> vaccine + status (the YF/cholera gate)
    dbo.FactMissionStaffingNeed-- open roles per active mission (the demand)

It reads the same seeded mirror the app uses (data/field_response/records.json), so
the seeded demo and the warehouse never drift. When you get a real Dynamics 365
workforce instance, replace `_load_records()` with a Link-to-Fabric view mapping the
real Dataverse entities onto these column names — nothing downstream changes.

Usage (only when you explicitly want to provision):
    $env:FIELDRESPONSE_SQL_SERVER = "<your-warehouse>.datawarehouse.fabric.microsoft.com"
    $env:FIELDRESPONSE_SQL_DATABASE = "fieldresponse_demo_FieldResponse_GD"
    python scripts/load_field_response_warehouse.py
"""
from __future__ import annotations

import json
import os
import struct
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = REPO_ROOT / "data" / "field_response" / "records.json"

SERVER = os.getenv("FIELDRESPONSE_SQL_SERVER", "")
DATABASE = os.getenv("FIELDRESPONSE_SQL_DATABASE", "fieldresponse_demo_FieldResponse_GD")
TENANT_ID = os.getenv("MISSIONIQ_TENANT_ID", "d97e8bab-6e30-49cc-9d1d-d1a4cd148170")

_SQL_COPT_SS_ACCESS_TOKEN = 1256
_TOKEN_SCOPE = "https://database.windows.net/.default"


# --- DDL: idempotent star schema -------------------------------------------

_DDL = [
    "DROP TABLE IF EXISTS dbo.FactStaffLanguage",
    "DROP TABLE IF EXISTS dbo.FactStaffVaccination",
    "DROP TABLE IF EXISTS dbo.FactMissionStaffingNeed",
    "DROP TABLE IF EXISTS dbo.dm_FieldStaff",
    "DROP TABLE IF EXISTS dbo.dm_Country",
    """
    CREATE TABLE dbo.dm_Country (
        CountryKey       INT NOT NULL,
        CountryName      VARCHAR(80) NOT NULL,
        Region           VARCHAR(80) NULL,
        BaselineRiskTier VARCHAR(20) NULL
    )
    """,
    """
    CREATE TABLE dbo.dm_FieldStaff (
        FieldStaffKey        INT NOT NULL,
        FullName             VARCHAR(120) NOT NULL,
        Email                VARCHAR(160) NULL,
        Phone                VARCHAR(40) NULL,
        PrimaryRole          VARCHAR(60) NULL,
        SpecialtyDetail      VARCHAR(200) NULL,
        HomeBase             VARCHAR(120) NULL,
        CurrentLocation      VARCHAR(120) NULL,
        CurrentCountryKey    INT NULL,
        CurrentStatus        VARCHAR(30) NULL,
        AvailableFrom        DATE NULL,
        RestUntil            DATE NULL,
        PassportExpiry       DATE NULL,
        SecurityClearance    VARCHAR(60) NULL,
        DeploymentsCompleted INT NULL,
        IsVeteran            BIT NULL,
        IsFirstMission       BIT NULL,
        Reliability          FLOAT NULL,
        Cleared              BIT NULL
    )
    """,
    """
    CREATE TABLE dbo.FactStaffLanguage (
        FieldStaffKey INT NOT NULL,
        Language      VARCHAR(40) NOT NULL,
        Proficiency   VARCHAR(20) NULL
    )
    """,
    """
    CREATE TABLE dbo.FactStaffVaccination (
        FieldStaffKey INT NOT NULL,
        Vaccine       VARCHAR(40) NOT NULL,
        Status        VARCHAR(20) NULL,
        Detail        VARCHAR(120) NULL
    )
    """,
    """
    CREATE TABLE dbo.FactMissionStaffingNeed (
        MissionName          VARCHAR(120) NOT NULL,
        RoleNeeded           VARCHAR(60) NOT NULL,
        HeadcountNeeded      INT NULL,
        HeadcountFilled      INT NULL,
        Priority             VARCHAR(20) NULL,
        LanguageRequired     VARCHAR(40) NULL,
        RequiredVaccinations VARCHAR(160) NULL,
        WindowHours          INT NULL
    )
    """,
]


def _connect():
    import pyodbc  # imported lazily so the module stays inert until run
    from missioniq.config import load_settings
    from missioniq.live import build_credential

    if not SERVER:
        sys.exit(
            "FIELDRESPONSE_SQL_SERVER is not set. Point it at your Fabric warehouse "
            "SQL endpoint before running this loader."
        )
    settings = load_settings()
    cred = build_credential(settings)  # tenant-pinned; same identity as provisioning
    token = cred.get_token(_TOKEN_SCOPE).token.encode("utf-16-le")
    tokstruct = struct.pack(f"<I{len(token)}s", len(token), token)
    cs = (
        f"Driver={{ODBC Driver 17 for SQL Server}};Server={SERVER};"
        f"Database={DATABASE};Encrypt=yes;TrustServerCertificate=no;"
    )
    return pyodbc.connect(cs, attrs_before={_SQL_COPT_SS_ACCESS_TOKEN: tokstruct})


def _load_records() -> dict[str, Any]:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def _country_of(location: str | None) -> str:
    if not location:
        return "Unknown"
    return location.split(",")[-1].strip() or "Unknown"


def _vax_status(value: str | None) -> tuple[str, str]:
    """('Current'|'Expired', original detail) from a field like 'expired 2026-01-15'."""
    v = (value or "").strip()
    status = "Expired" if v.lower().startswith("expired") or "lapsed" in v.lower() else "Current"
    return status, v


def _date_or_none(value: str | None) -> str | None:
    return value or None


def main() -> None:
    data = _load_records()
    records = data.get("records", [])
    needs = data.get("needs", [])

    # Build the country dimension from every location we see.
    countries: dict[str, int] = {}
    for r in records:
        for loc in (r.get("current_location"), r.get("home_base")):
            c = _country_of(loc)
            if c not in countries:
                countries[c] = len(countries) + 1

    conn = _connect()
    cur = conn.cursor()

    print(f"Provisioning schema in {DATABASE} ...")
    for stmt in _DDL:
        cur.execute(stmt)
    conn.commit()

    # dm_Country
    for name, key in countries.items():
        cur.execute(
            "INSERT INTO dbo.dm_Country (CountryKey, CountryName, Region, BaselineRiskTier) "
            "VALUES (?, ?, ?, ?)",
            key, name, None, "Standard",
        )

    # dm_FieldStaff + child facts
    for i, r in enumerate(records, start=1):
        cur.execute(
            """INSERT INTO dbo.dm_FieldStaff
               (FieldStaffKey, FullName, Email, Phone, PrimaryRole, SpecialtyDetail,
                HomeBase, CurrentLocation, CurrentCountryKey, CurrentStatus,
                AvailableFrom, RestUntil, PassportExpiry, SecurityClearance,
                DeploymentsCompleted, IsVeteran, IsFirstMission, Reliability, Cleared)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            i, r.get("name"), r.get("email"), r.get("phone"), r.get("role"),
            r.get("specialty"), r.get("home_base"), r.get("current_location"),
            countries.get(_country_of(r.get("current_location"))), r.get("status"),
            _date_or_none(r.get("available_from")), _date_or_none(r.get("rest_until")),
            _date_or_none(r.get("passport_expiry")), r.get("security_clearance"),
            r.get("deployments_completed"), 1 if r.get("veteran") else 0,
            1 if r.get("first_mission") else 0, r.get("reliability"),
            1 if r.get("cleared") else 0,
        )
        for lang in r.get("languages", []):
            cur.execute(
                "INSERT INTO dbo.FactStaffLanguage (FieldStaffKey, Language, Proficiency) "
                "VALUES (?, ?, ?)",
                i, lang, "Fluent",
            )
        for vaccine, field_val in (("Yellow Fever", r.get("yellow_fever")),
                                   ("Cholera", r.get("cholera_vax"))):
            status, detail = _vax_status(field_val)
            cur.execute(
                "INSERT INTO dbo.FactStaffVaccination (FieldStaffKey, Vaccine, Status, Detail) "
                "VALUES (?, ?, ?, ?)",
                i, vaccine, status, detail,
            )

    # FactMissionStaffingNeed
    for n in needs:
        cur.execute(
            """INSERT INTO dbo.FactMissionStaffingNeed
               (MissionName, RoleNeeded, HeadcountNeeded, HeadcountFilled, Priority,
                LanguageRequired, RequiredVaccinations, WindowHours)
               VALUES (?,?,?,?,?,?,?,?)""",
            n.get("mission"), n.get("role"), n.get("headcount_needed"),
            n.get("headcount_filled"), n.get("priority"), n.get("language_required"),
            ", ".join(n.get("required_vaccinations", [])), n.get("window_hours"),
        )

    conn.commit()
    print(
        f"Loaded {len(records)} staff, {len(countries)} countries, "
        f"{len(needs)} mission needs into {DATABASE}."
    )


if __name__ == "__main__":
    sys.path.insert(0, str(REPO_ROOT / "src"))
    main()
