"""Guardrail tests: the agent can flag, but can never edit an order.

Needs the database running:  docker compose up -d
"""
import asyncio
import sys
from pathlib import Path

import psycopg
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))
import server as srv  # noqa: E402


def test_server_exposes_only_the_two_read_only_tools():
    tools = asyncio.run(srv.mcp.list_tools())
    assert {t.name for t in tools} == {"find_late_orders", "flag_address_mismatch"}
    assert all(t.annotations and t.annotations.readOnlyHint for t in tools)


def test_agent_role_is_read_only_by_default():
    """The agent_ro role starts every transaction read-only (ALTER ROLE ... SET)."""
    with psycopg.connect(srv.DATABASE_URL) as conn:
        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
            conn.execute("UPDATE orders SET tracking_status = 'delivered'")


def test_agent_role_has_no_write_privilege():
    """Layer 3, tested on its own: even if read-only mode is switched OFF,
    the role has no UPDATE/DELETE/INSERT grant, so Postgres still refuses."""
    with psycopg.connect(srv.DATABASE_URL) as conn:
        conn.execute("SET SESSION CHARACTERISTICS AS TRANSACTION READ WRITE")
        conn.execute("SET transaction_read_only = off")
        for sql in ("UPDATE orders SET tracking_status = 'delivered'",
                    "DELETE FROM orders",
                    "INSERT INTO orders (order_number) VALUES ('X')"):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(sql)
            conn.rollback()
            conn.execute("SET transaction_read_only = off")


def test_read_only_session_blocks_writes_even_for_a_privileged_role():
    """Layer 2: a read-only session refuses writes regardless of role permissions."""
    admin = srv.DATABASE_URL.replace("agent_ro:agent_ro_pw", "ops_admin:ops_admin_pw")
    with psycopg.connect(admin) as conn:
        conn.read_only = True
        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
            conn.execute("UPDATE orders SET tracking_status = 'delivered'")


def test_tools_return_expected_planted_problems():
    late = srv.find_late_orders(7)
    assert late["count"] >= 10
    assert any(o["risk_level"] == "high" for o in late["orders"])
    addr = srv.flag_address_mismatch()
    assert sum(1 for o in addr["orders"] if o["risk_level"] == "high") == 3   # 3 ZIP mismatches
    assert sum(1 for o in addr["orders"] if o["risk_level"] == "medium") == 2  # 2 missing numbers
