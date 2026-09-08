"""Tests for ClickHouse Model Context Protocol (MCP) Server (P5)."""
from __future__ import annotations

import json

from doctus.analytics.clickhouse import ClickHouseConfig, ClickHouseMirror
from doctus.mcp.clickhouse_server import ClickHouseMcpServer


def test_clickhouse_mcp_list_tools():
    server = ClickHouseMcpServer(ClickHouseMirror(ClickHouseConfig(mock_mode=True)))
    tools = server.list_tools()
    names = {t["name"] for t in tools}
    assert "doctus_query_decisions" in names
    assert "doctus_gate_metrics" in names
    assert "doctus_deny_reasons" in names
    assert "doctus_expiring_licenses" in names
    assert "doctus_chain_depth" in names
    assert "doctus_executive_summary" in names


def test_clickhouse_mcp_call_tools():
    mirror = ClickHouseMirror(ClickHouseConfig(mock_mode=True))
    mirror.stream_decision({
        "decision_id": 1,
        "ts": "2026-08-30T10:00:00Z",
        "asset_id": "ast_mcp_test",
        "verb": "publish",
        "allowed": 0,
        "reason": "SCOPE_EXCEEDED",
        "detail": "trailer not covered",
        "latency_ms": 1.25,
    })

    server = ClickHouseMcpServer(mirror)

    # 1. gate metrics
    res_metrics = server.call_tool("doctus_gate_metrics", {})
    assert not res_metrics["isError"]
    assert res_metrics["data"]["count"] == 1
    assert res_metrics["data"]["p50"] == 1.25

    # 2. query decisions
    res_decisions = server.call_tool("doctus_query_decisions", {"asset_id": "ast_mcp_test"})
    assert not res_decisions["isError"]
    assert len(res_decisions["data"]) == 1
    assert res_decisions["data"][0]["reason"] == "SCOPE_EXCEEDED"

    # 3. deny reasons
    res_reasons = server.call_tool("doctus_deny_reasons", {})
    assert not res_reasons["isError"]
    assert res_reasons["data"]["SCOPE_EXCEEDED"] == 1

    # 4. executive summary
    res_summary = server.call_tool("doctus_executive_summary", {})
    assert not res_summary["isError"]
    assert res_summary["data"]["gate_decisions"] == 1
    assert res_summary["data"]["denies"] == 1

    # 5. unknown tool
    res_unknown = server.call_tool("unknown_tool", {})
    assert res_unknown["isError"]


def test_clickhouse_mcp_jsonrpc_protocol():
    mirror = ClickHouseMirror(ClickHouseConfig(mock_mode=True))
    server = ClickHouseMcpServer(mirror)

    init_req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {},
    }
    init_res = server._handle_jsonrpc(init_req)
    assert init_res["result"]["serverInfo"]["name"] == "doctus-clickhouse-mcp"

    list_req = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {},
    }
    list_res = server._handle_jsonrpc(list_req)
    assert len(list_res["result"]["tools"]) >= 6

    call_req = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": "doctus_gate_metrics", "arguments": {}},
    }
    call_res = server._handle_jsonrpc(call_req)
    assert not call_res["result"]["isError"]
