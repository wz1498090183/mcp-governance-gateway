# -*- coding: utf-8 -*-
"""运维端点 /health /ready 单元测试。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from fakes import FakeAdapter
from mcp_gateway.main import create_app
from mcp_gateway.registry import MCPRegistry


def _make_client() -> TestClient:
    registry = MCPRegistry(adapters={"demo": FakeAdapter("demo", ["echo"])})
    return TestClient(create_app(registry))


def test_health_ok() -> None:
    with _make_client() as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


def test_ready_ok() -> None:
    with _make_client() as client:
        resp = client.get("/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ready"
        assert data["servers"]["demo"]["ready"] is True
