"""ClickHouse Model Context Protocol (MCP) Server (P5, DESIGN.md §3.5).

Exposes studio-scale clearance analytics to Gemini and ADK agents via standard
MCP tools over stdio JSON-RPC.

Tools provided:
  - doctus_query_decisions: Search clearance decisions with filter criteria
  - doctus_gate_metrics: Gate latency percentiles (p50, p90, p95, p99)
  - doctus_deny_reasons: Histogram of compliance denial reasons
  - doctus_expiring_licenses: Proactive alerts on licenses expiring soon
  - doctus_chain_depth: Provenance derivation chain depth and complexity
  - doctus_executive_summary: Studio-wide clearance health and E&O audit metrics
"""
from __future__ import annotations

import json
import sys
from typing import Any, Callable

from doctus.analytics.clickhouse import ClickHouseConfig, ClickHouseMirror

TOOL_DEFINITIONS = [
    {
        "name": "doctus_query_decisions",
        "description": "Query historical clearance gate decisions with optional filters.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "asset_id": {"type": "string", "description": "Optional asset ID filter"},
                "allowed": {"type": "boolean", "description": "Filter by allow (true) or deny (false)"},
                "limit": {"type": "integer", "description": "Max rows to return (default 20)"},
            },
        },
    },
    {
        "name": "doctus_gate_metrics",
        "description": "Retrieve gate lookup latency percentiles (p50, p90, p95, p99 in ms).",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "doctus_deny_reasons",
        "description": "Retrieve histogram breakdown of clearance denial reasons across the studio.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "doctus_expiring_licenses",
        "description": "Alert on assets whose licenses/consents expire within a given threshold of days.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "within_days": {"type": "integer", "description": "Days lookahead window (default 30)"},
            },
        },
    },
    {
        "name": "doctus_chain_depth",
        "description": "Analyze provenance chain depth, ingredient count, and clearance outcome per asset.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "doctus_executive_summary",
        "description": "Get high-level studio clearance rate, asset counts, and E&O insurability metrics.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
]


class ClickHouseMcpServer:
    """MCP Server exposing ClickHouse rights analytics to AI agents."""

    def __init__(self, mirror: ClickHouseMirror | None = None) -> None:
        self.mirror = mirror or ClickHouseMirror()
        self._tools: dict[str, Callable[[dict[str, Any]], Any]] = {
            "doctus_query_decisions": self._handle_query_decisions,
            "doctus_gate_metrics": self._handle_gate_metrics,
            "doctus_deny_reasons": self._handle_deny_reasons,
            "doctus_expiring_licenses": self._handle_expiring_licenses,
            "doctus_chain_depth": self._handle_chain_depth,
            "doctus_executive_summary": self._handle_executive_summary,
        }

    def list_tools(self) -> list[dict[str, Any]]:
        return TOOL_DEFINITIONS

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        handler = self._tools.get(name)
        if not handler:
            return {"isError": True, "content": [{"type": "text", "text": f"Unknown tool '{name}'"}]}
        try:
            result = handler(arguments or {})
            return {
                "isError": False,
                "content": [{"type": "text", "text": json.dumps(result, indent=2)}],
                "data": result,
            }
        except Exception as exc:
            return {
                "isError": True,
                "content": [{"type": "text", "text": f"Error executing {name}: {exc}"}],
            }

    # -------------------------------------------------------- Tool Handlers
    def _handle_query_decisions(self, args: dict[str, Any]) -> list[dict[str, Any]]:
        decisions = self.mirror._get_table_rows("doctus_decisions")
        filtered = decisions
        if "asset_id" in args and args["asset_id"]:
            filtered = [d for d in filtered if d.get("asset_id") == args["asset_id"]]
        if "allowed" in args and args["allowed"] is not None:
            filtered = [d for d in filtered if bool(d.get("allowed")) == bool(args["allowed"])]
        limit = int(args.get("limit", 20))
        return filtered[:limit]

    def _handle_gate_metrics(self, args: dict[str, Any]) -> dict[str, Any]:
        return self.mirror.get_gate_latency_percentiles()

    def _handle_deny_reasons(self, args: dict[str, Any]) -> dict[str, Any]:
        return self.mirror.get_deny_reasons_histogram()

    def _handle_expiring_licenses(self, args: dict[str, Any]) -> list[dict[str, Any]]:
        within_days = int(args.get("within_days", 30))
        return self.mirror.get_expiring_window_alerts(within_days=within_days)

    def _handle_chain_depth(self, args: dict[str, Any]) -> list[dict[str, Any]]:
        return self.mirror.get_chain_depth_vs_clearance()

    def _handle_executive_summary(self, args: dict[str, Any]) -> dict[str, Any]:
        return self.mirror.get_studio_executive_summary()

    # ---------------------------------------------------- JSON-RPC Loop
    def run_stdio(self) -> None:
        """Process standard JSON-RPC 2.0 messages from stdin to stdout."""
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
                res = self._handle_jsonrpc(req)
                sys.stdout.write(json.dumps(res) + "\n")
                sys.stdout.flush()
            except Exception as exc:
                err_res = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32603, "message": str(exc)},
                }
                sys.stdout.write(json.dumps(err_res) + "\n")
                sys.stdout.flush()

    def _handle_jsonrpc(self, req: dict[str, Any]) -> dict[str, Any]:
        msg_id = req.get("id")
        method = req.get("method")
        params = req.get("params", {})

        if method == "tools/list":
            return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": self.list_tools()}}
        elif method == "tools/call":
            tool_name = params.get("name", "")
            tool_args = params.get("arguments", {})
            res = self.call_tool(tool_name, tool_args)
            return {"jsonrpc": "2.0", "id": msg_id, "result": res}
        elif method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "doctus-clickhouse-mcp", "version": "0.1.0"},
                },
            }
        else:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }


if __name__ == "__main__":
    server = ClickHouseMcpServer()
    server.run_stdio()
