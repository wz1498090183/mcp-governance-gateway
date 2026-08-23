# -*- coding: utf-8 -*-
"""REST API 单元测试（使用 FakeAdapter，覆盖正常 / 不存在 / 异常场景）。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from fakes import FakeAdapter
from mcp_gateway.main import create_app
from mcp_gateway.registry import MCPRegistry


def _make_client(tool_names: list[str], fail_calls: bool = False) -> TestClient:
    """构造注入 FakeAdapter 的测试客户端。"""
    registry = MCPRegistry(adapters={"demo": FakeAdapter("demo", tool_names, fail_calls)})
    return TestClient(create_app(registry))


def test_list_tools_ok() -> None:
    with _make_client(["echo", "sleep"]) as client:
        resp = client.get("/api/v1/tools")
        assert resp.status_code == 200
        data = resp.json()
        names = {t["name"] for t in data["tools"]}
        assert names == {"echo", "sleep"}
        for tool in data["tools"]:
            assert tool["server_id"] == "demo"


def test_call_tool_ok() -> None:
    with _make_client(["echo"]) as client:
        resp = client.post("/api/v1/tools/demo/echo/call", json={"text": "hello"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_error"] is False
        assert data["content"][0]["text"] == "echo:hello"


def test_call_tool_server_not_found() -> None:
    with _make_client(["echo"]) as client:
        resp = client.post("/api/v1/tools/nope/echo/call", json={"text": "x"})
        assert resp.status_code == 404


def test_call_tool_not_found() -> None:
    with _make_client(["echo"]) as client:
        resp = client.post("/api/v1/tools/demo/nope/call", json={"text": "x"})
        assert resp.status_code == 404


def test_call_tool_adapter_error() -> None:
    with _make_client(["echo"], fail_calls=True) as client:
        resp = client.post("/api/v1/tools/demo/echo/call", json={"text": "x"})
        assert resp.status_code == 502
