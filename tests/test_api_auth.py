# -*- coding: utf-8 -*-
"""鉴权下的 REST API 集成测试（FakeAdapter + 手动签发 Token）。"""

from __future__ import annotations

from mcp_gateway.config import ToolPolicyRule

from jwt_helpers import build_token, make_auth_client


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---- 工具发现 ----


def test_list_tools_valid_token() -> None:
    with make_auth_client() as client:
        token = build_token(roles=["analyst"], scope="tools:list tools:call")
        resp = client.get("/api/v1/tools", headers=_bearer(token))
        assert resp.status_code == 200
        names = {t["name"] for t in resp.json()["tools"]}
        assert names == {"echo", "sleep"}


def test_list_tools_no_token() -> None:
    with make_auth_client() as client:
        resp = client.get("/api/v1/tools")
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTH_INVALID_TOKEN"


def test_list_tools_missing_list_scope() -> None:
    with make_auth_client() as client:
        token = build_token(roles=["analyst"], scope="")  # 无 tools:list
        resp = client.get("/api/v1/tools", headers=_bearer(token))
        assert resp.status_code == 403
        assert resp.json()["code"] == "AUTH_INSUFFICIENT_SCOPE"


def test_list_tools_filtered_by_policy() -> None:
    # 只给 echo 配置 discover 策略，sleep 应被过滤掉
    policies = [
        ToolPolicyRule(tenant="tenant-a", role="analyst", server="demo", tool="echo", actions=["discover", "call"]),
    ]
    with make_auth_client(policies=policies) as client:
        token = build_token(roles=["analyst"], scope="tools:list tools:call")
        resp = client.get("/api/v1/tools", headers=_bearer(token))
        assert resp.status_code == 200
        names = {t["name"] for t in resp.json()["tools"]}
        assert names == {"echo"}


def test_list_tools_guest_sees_nothing() -> None:
    with make_auth_client() as client:
        token = build_token(roles=["guest"], scope="tools:list tools:call")
        resp = client.get("/api/v1/tools", headers=_bearer(token))
        assert resp.status_code == 200
        assert resp.json()["tools"] == []


# ---- 工具调用 ----


def test_call_tool_ok() -> None:
    with make_auth_client() as client:
        token = build_token(roles=["analyst"], scope="tools:list tools:call")
        resp = client.post("/api/v1/tools/demo/echo/call", headers=_bearer(token), json={"text": "hi"})
        assert resp.status_code == 200
        assert resp.json()["content"][0]["text"] == "echo:hi"


def test_call_tool_no_token() -> None:
    with make_auth_client() as client:
        resp = client.post("/api/v1/tools/demo/echo/call", json={"text": "hi"})
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTH_INVALID_TOKEN"


def test_call_tool_wrong_audience() -> None:
    with make_auth_client() as client:
        token = build_token(roles=["analyst"], scope="tools:list tools:call", aud="other-audience")
        resp = client.post("/api/v1/tools/demo/echo/call", headers=_bearer(token), json={"text": "hi"})
        assert resp.status_code == 401


def test_call_tool_missing_call_scope() -> None:
    with make_auth_client() as client:
        token = build_token(roles=["analyst"], scope="")  # 缺 tools:call
        resp = client.post("/api/v1/tools/demo/echo/call", headers=_bearer(token), json={"text": "hi"})
        assert resp.status_code == 403
        assert resp.json()["code"] == "AUTH_INSUFFICIENT_SCOPE"


def test_call_tool_guest_denied() -> None:
    with make_auth_client() as client:
        token = build_token(roles=["guest"], scope="tools:list tools:call")
        resp = client.post("/api/v1/tools/demo/echo/call", headers=_bearer(token), json={"text": "hi"})
        assert resp.status_code == 403
        assert resp.json()["code"] == "POLICY_TOOL_DENIED"
