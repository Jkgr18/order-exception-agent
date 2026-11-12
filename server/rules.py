"""Business rules, as PURE functions (no database, no MCP). Easy to unit test.

The model never decides what "late" or "bad address" means; these rules do.
The model's job is to call the tools, then explain the results in plain language.
"""
from __future__ import annotations

import re
from datetime import date, datetime

# Valid 3-digit ZIP prefix ranges per state (subset, enough for the demo data).
ZIP_PREFIXES = {
    "CA": (900, 961), "NY": (100, 149), "TX": (750, 799), "FL": (320, 349),
    "IL": (600, 629), "WA": (980, 994), "GA": (300, 319), "CO": (800, 816),
}

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def zip_matches_state(state: str, zip_code: str) -> bool | None:
    """True/False if we can tell, None if the state isn't in our table."""
    rng = ZIP_PREFIXES.get(state)
    if rng is None:
        return None
    if not re.fullmatch(r"\d{5}", zip_code or ""):
        return False
    return rng[0] <= int(zip_code[:3]) <= rng[1]


def assess_delivery_risk(order: dict, today: date, horizon_days: int = 7) -> list[dict]:
    """Return a list of {severity, reason} for one order (empty list = no risk)."""
    if order["tracking_status"] in ("delivered", "returned"):
        return []

    findings: list[dict] = []
    status = order["tracking_status"]
    scan: datetime | None = order["last_scan_at"]
    days_since_ship = (today - order["ship_date"]).days
    days_to_promise = (order["promised_date"] - today).days

    if status == "exception":
        findings.append({"severity": "high",
                         "reason": f"Carrier reported a delivery exception ({order['last_scan_location']})"})
    if days_to_promise < 0:
        findings.append({"severity": "high",
                         "reason": f"Overdue: promised {order['promised_date']}, {-days_to_promise} day(s) ago"})
    if scan is None and days_since_ship >= 2:
        findings.append({"severity": "high",
                         "reason": f"No carrier scan {days_since_ship} days after ship date (label created, package may never have been picked up)"})
    if scan is not None and status in ("in_transit", "out_for_delivery"):
        idle = (today - scan.date()).days
        if idle >= 3:
            findings.append({"severity": "medium",
                             "reason": f"Stalled: no scan for {idle} days (last: {order['last_scan_location']})"})

    # Only report orders whose promise date falls inside the window (or is already past).
    if findings and days_to_promise > horizon_days:
        return []
    return findings


def assess_address(order: dict) -> list[dict]:
    """Return a list of {severity, reason} address problems for one order."""
    findings: list[dict] = []
    ok = zip_matches_state(order["ship_state"], order["ship_zip"])
    if ok is False:
        findings.append({"severity": "high",
                         "reason": f"ZIP {order['ship_zip']} does not belong to state {order['ship_state']}"})
    if not re.match(r"^\s*\d", order["ship_address1"]):
        findings.append({"severity": "medium",
                         "reason": f"Street address has no house number: '{order['ship_address1']}'"})
    if (order["ship_state"], order["ship_zip"]) != (order["bill_state"], order["bill_zip"]):
        findings.append({"severity": "low",
                         "reason": f"Ships to {order['ship_state']} {order['ship_zip']} but billed in "
                                   f"{order['bill_state']} {order['bill_zip']} (often a gift; informational)"})
    return findings


def top_severity(findings: list[dict]) -> str:
    return min((f["severity"] for f in findings), key=SEVERITY_ORDER.get)
