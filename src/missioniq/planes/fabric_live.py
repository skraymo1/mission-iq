"""Live Fabric provider — the real structured plane, on real OneLake data.

This is the go-live swap made real: instead of reading a seeded JSON mirror, the
fundraising skin's Fabric plane queries the **gold lakehouse SQL endpoint** of the
Microsoft Cloud for Nonprofit *Fundraising & Engagement* model in OneLake, over
the Tabular Data Stream with the caller's Entra ID token (no keys, read-only).

Everything above this layer is identical to the seeded path: the orchestrator
just calls a tool and gets back ranked records.
"""
from __future__ import annotations

import datetime
import struct
from decimal import Decimal
from typing import Any

import pyodbc
from azure.identity import DefaultAzureCredential

# Gold lakehouse SQL endpoint (workspace: Fundraising demo).
SERVER = "vofx5wjqn3gethi52gsm2feboa-pnbvln5xlwme7cupqu46lp2qhm.datawarehouse.fabric.microsoft.com"
DATABASE = "fundraising_demo_Fundraising_GD"

_SQL_COPT_SS_ACCESS_TOKEN = 1256
_TOKEN_SCOPE = "https://database.windows.net/.default"

# Ordinal rank for the wealth-screening capacity bands, so we can sort by it.
CAPACITY_RANK = {
    "Under $10,000": 1,
    "$10,000 - $49,999": 2,
    "$50,000 - $99,999": 3,
    "$100,000 - $499,999": 4,
    "$500,000 - $999,999": 5,
    "$1,000,000+": 6,
}
RATING_RANK = {"Low": 1, "Medium": 2, "High": 3, "Exceptional": 4}

# Donors fetched once and joined across the giving + wealth + date marts.
_FETCH_SQL = """
SELECT
    c.ConstituentName, c.Email, c.Age, c.EngagementStage, c.AcquisitionChannel,
    c.LifetimeDonationAmount, c.IsNewDonor,
    w.CapacityRange, w.ConstituentRating,
    ld.Date AS LastDonationDate
FROM dbo.dm_Constituent c
LEFT JOIN dbo.FactWealthScreening w ON w.ConstituentKey = c.ConstituentKey
LEFT JOIN dbo.DimDate ld ON ld.DateKey = c.LastDonationDateKey
WHERE c.LifetimeDonationAmount IS NOT NULL
"""

_credential: DefaultAzureCredential | None = None
_conn: "pyodbc.Connection | None" = None


def _get_credential() -> DefaultAzureCredential:
    global _credential
    if _credential is None:
        _credential = DefaultAzureCredential()
    return _credential


def _connect() -> "pyodbc.Connection":
    token = _get_credential().get_token(_TOKEN_SCOPE).token.encode("utf-16-le")
    tokstruct = struct.pack(f"<I{len(token)}s", len(token), token)
    cs = (
        f"Driver={{ODBC Driver 17 for SQL Server}};Server={SERVER};"
        f"Database={DATABASE};Encrypt=yes;TrustServerCertificate=no;"
    )
    return pyodbc.connect(cs, attrs_before={_SQL_COPT_SS_ACCESS_TOKEN: tokstruct})


def _cursor():
    """Cached connection, reconnecting once if the token/connection went stale."""
    global _conn
    if _conn is None:
        _conn = _connect()
    try:
        return _conn.cursor()
    except pyodbc.Error:
        _conn = _connect()
        return _conn.cursor()


def _rows() -> list[dict[str, Any]]:
    cur = _cursor()
    cur.execute(_FETCH_SQL)
    cols = [d[0] for d in cur.description]
    out: list[dict[str, Any]] = []
    for r in cur.fetchall():
        out.append({c: v for c, v in zip(cols, r)})
    return out


def _lapsed_days(last: datetime.date | None, today: datetime.date) -> int | None:
    if not last:
        return None
    return (today - last).days


def fetch_donors(
    filter_text: str,
    today: datetime.date | None = None,
    top: int = 8,
) -> dict[str, Any]:
    """Query live donors from the Fabric gold lakehouse, ranked for the filter.

    Scores each constituent by keyword overlap with the request, then boosts by
    giving capacity, donor rating, lifetime value, and how overdue they are for a
    touch (lapsed days) so high-value, at-risk donors surface first. Returns the
    top matches plus a portfolio summary that frames the demand.
    """
    today = today or datetime.date.today()
    rows = _rows()

    tokens = [
        t
        for t in "".join(ch if ch.isalnum() else " " for ch in filter_text.lower()).split()
        if len(t) > 2
    ]

    scored: list[tuple[float, dict[str, Any]]] = []
    for r in rows:
        cap_rank = CAPACITY_RANK.get(r.get("CapacityRange"), 0)
        rating_rank = RATING_RANK.get(r.get("ConstituentRating"), 0)
        lifetime = float(r.get("LifetimeDonationAmount") or 0)
        lapsed = _lapsed_days(r.get("LastDonationDate"), today)

        blob = " ".join(str(v) for v in r.values()).lower()
        score = sum(1.0 for t in tokens if t in blob)
        score += cap_rank * 0.8           # giving capacity matters most
        score += rating_rank * 0.4        # screened donor rating
        score += min(lifetime / 50000.0, 5.0)  # lifetime value, capped
        if lapsed is not None and lapsed > 270:
            score += 1.5                  # overdue for a touch
        scored.append((score, _present(r, lapsed)))

    scored.sort(key=lambda x: x[0], reverse=True)
    matches = [rec for _, rec in scored[:top]]

    # Portfolio framing = the "demand" for this mission.
    major = [
        r
        for r in rows
        if CAPACITY_RANK.get(r.get("CapacityRange"), 0) >= 4
    ]
    lapsed_major = [
        r
        for r in major
        if (d := _lapsed_days(r.get("LastDonationDate"), today)) is not None and d > 270
    ]
    at_risk_value = sum(float(r.get("LifetimeDonationAmount") or 0) for r in lapsed_major)

    return {
        "entity": "constituents",
        "as_of": today.isoformat(),
        "portfolio": {
            "total_constituents": len(rows),
            "major_capacity_donors": len(major),
            "lapsed_major_donors_over_9mo": len(lapsed_major),
            "lifetime_value_at_risk": round(at_risk_value, 2),
        },
        "matches": matches,
        "source": "Fabric gold lakehouse · dm_Constituent ⋈ FactWealthScreening (live)",
    }


def _present(r: dict[str, Any], lapsed: int | None) -> dict[str, Any]:
    last = r.get("LastDonationDate")
    return {
        "name": r.get("ConstituentName"),
        "email": r.get("Email"),
        "age": r.get("Age"),
        "engagement_stage": r.get("EngagementStage"),
        "acquisition_channel": r.get("AcquisitionChannel"),
        "lifetime_giving": float(r["LifetimeDonationAmount"])
        if isinstance(r.get("LifetimeDonationAmount"), Decimal)
        else r.get("LifetimeDonationAmount"),
        "capacity_range": r.get("CapacityRange"),
        "wealth_rating": r.get("ConstituentRating"),
        "last_donation": last.isoformat() if last else None,
        "days_since_last_gift": lapsed,
        "new_donor": bool(r.get("IsNewDonor")),
    }
