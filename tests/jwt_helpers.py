# -*- coding: utf-8 -*-
"""鉴权测试辅助：签发 JWT、构建带鉴权的 TestClient。"""

from __future__ import annotations

import time

import jwt
from fastapi.testclient import TestClient

from fakes import FakeAdapter
from mcp_gateway.config import ToolPolicyRule
from mcp_gateway.main import create_app
from mcp_gateway.registry import MCPRegistry
from mcp_gateway.security import Security
from mcp_gateway.security.policy import PolicyEngine
from mcp_gateway.security.verifier import HS256TokenVerifier

TEST_SECRET = "test-secret-key-for-mcp-gateway-0123456789abcdef"
ISSUER = "mcp-gateway-dev"
AUDIENCE = "mcp-gateway"
TENANT = "tenant-a"

DEFAULT_POLICIES = [
    ToolPolicyRule(tenant=TENANT, role="analyst", server="demo", tool="echo", actions=["discover", "call"]),
    ToolPolicyRule(tenant=TENANT, role="analyst", server="demo", tool="sleep", actions=["discover", "call"]),
]


def build_token(
    *,
    sub: str = "u-test",
    tenant_id: str = TENANT,
    roles: list[str] | None = None,
    scope: str = "",
    aud: str = AUDIENCE,
    issuer: str = ISSUER,
    algorithm: str = "HS256",
    expired: bool = False,
) -> str:
    """构造 HS256 JWT，可按需覆盖字段覆盖各类鉴权场景。"""
    now = int(time.time())
    payload = {
        "sub": sub,
        "tenant_id": tenant_id,
        "roles": roles or [],
        "scope": scope,
        "iss": issuer,
        "aud": aud,
        "iat": now,
        "exp": now - 10 if expired else now + 3600,
    }
    return jwt.encode(payload, TEST_SECRET, algorithm=algorithm)


def _make_security(policies: list[ToolPolicyRule]) -> Security:
    verifier = HS256TokenVerifier(secret=TEST_SECRET, issuer=ISSUER, audience=AUDIENCE)
    return Security(verifier=verifier, policy=PolicyEngine(policies))


def make_auth_client(
    tool_names: list[str] | None = None,
    policies: list[ToolPolicyRule] | None = None,
    governance=None,
    fail_timeout: bool = False,
) -> TestClient:
    """构建注入 FakeAdapter、Security 与 Governance 的测试客户端。"""
    names = tool_names if tool_names is not None else ["echo", "sleep"]
    rules = policies if policies is not None else DEFAULT_POLICIES
    registry = MCPRegistry(adapters={"demo": FakeAdapter("demo", names, fail_timeout=fail_timeout)})
    return TestClient(create_app(registry, _make_security(rules), governance))
