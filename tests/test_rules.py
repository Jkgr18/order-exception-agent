"""Unit tests for the business rules. No database needed."""
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))
from rules import assess_address, assess_delivery_risk, zip_matches_state  # noqa: E402

TODAY = date(2026, 11, 12)


def make(**kw):
    base = dict(
        tracking_status="in_transit", ship_date=TODAY - timedelta(days=2),
        promised_date=TODAY + timedelta(days=3),
        last_scan_at=datetime(2026, 11, 12, 9, 0), last_scan_location="Hub",
        ship_address1="12 Maple St", ship_city="Austin", ship_state="TX", ship_zip="78701",
        bill_city="Austin", bill_state="TX", bill_zip="78701",
    )
    return {**base, **kw}


def test_healthy_order_has_no_risk():
    assert assess_delivery_risk(make(), TODAY) == []


def test_delivered_never_flagged():
    assert assess_delivery_risk(make(tracking_status="delivered", promised_date=TODAY - timedelta(days=5)), TODAY) == []


def test_overdue_is_high():
    f = assess_delivery_risk(make(promised_date=TODAY - timedelta(days=1)), TODAY)
    assert f and f[0]["severity"] == "high"


def test_never_scanned_is_high():
    f = assess_delivery_risk(make(tracking_status="label_created", last_scan_at=None,
                                  ship_date=TODAY - timedelta(days=3)), TODAY)
    assert any("No carrier scan" in x["reason"] for x in f)


def test_stalled_in_transit():
    f = assess_delivery_risk(make(last_scan_at=datetime(2026, 11, 7, 9, 0)), TODAY)
    assert any("Stalled" in x["reason"] for x in f)


def test_far_future_promise_outside_window_is_ignored():
    f = assess_delivery_risk(make(last_scan_at=datetime(2026, 11, 7, 9, 0),
                                  promised_date=TODAY + timedelta(days=20)), TODAY)
    assert f == []


def test_zip_state_mismatch():
    assert zip_matches_state("TX", "78701") is True
    assert zip_matches_state("TX", "10001") is False
    assert zip_matches_state("TX", "7870") is False
    assert zip_matches_state("ZZ", "12345") is None


def test_address_flags():
    assert assess_address(make()) == []
    assert assess_address(make(ship_zip="10001"))[0]["severity"] == "high"
    assert assess_address(make(ship_address1="Maple Street"))[0]["severity"] == "medium"
    gift = assess_address(make(bill_state="NY", bill_zip="10001"))
    assert [x["severity"] for x in gift] == ["low"]
