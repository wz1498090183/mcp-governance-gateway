# -*- coding: utf-8 -*-
"""JWT 验证器与策略引擎单元测试。"""

from __future__ import annotations

import time

import jwt as pyjwt
import pytest

from jwt_helpers import AUDIENCE, DEFAULT_POLICIES, ISSUER, TEST_SECRET, build_token
from mcp_gateway.config import AuthSettings, GatewayConfig, JWTSettings, ToolPolicyRule
from mcp_gateway.errors import AuthenticationError, InsufficientScopeError
from mcp_gateway.security import Principal, Security
from mcp_gateway.security.policy import PolicyEngine
from mcp_gateway.security.verifier import HS256TokenVerifier


def _verifier() -> HS256TokenVerifier:
    return HS256TokenVerifier(secret=TEST_SECRET, issuer=ISSUER, audience=AUDIENCE)


def _principal(
    roles: tuple[str, ...] = ("analyst",),
    scopes: tuple[str, ...] = ("tools:call",),
    tenant: str = "tenant-a",
) -> Principal:
    return Principal(sub="u", tenant_id=tenant, roles=roles, scopes=frozenset(scopes))


# ---- 验证器 ----


def test_verify_ok_extracts_fields() -> None:
    token = build_token(sub="u-1", roles=["analyst"], scope="tools:list tools:call")
    principal = _verifier().verify(token)
    assert principal.sub == "u-1"
    assert principal.tenant_id == "tenant-a"
    assert principal.roles == ("analyst",)
    assert principal.scopes == frozenset({"tools:list", "tools:call"})


def test_verify_scope_single() -> None:
    token = build_token(scope="tools:list")
    assert _verifier().verify(token).scopes == frozenset({"tools:list"})


def test_verify_wrong_signature() -> None:
    token = build_token(roles=["analyst"], scope="tools:list")
    other = HS256TokenVerifier(secret="wrong-secret-key-for-mcp-gateway-9876543210", issuer=ISSUER, audience=AUDIENCE)
    with pytest.raises(AuthenticationError):
        other.verify(token)


def test_verify_wrong_algorithm() -> None:
    # 用 HS512 签名，验证器固定 HS256，必须拒绝算法混淆
    token = build_token(algorithm="HS512")
    with pytest.raises(AuthenticationError):
        _verifier().verify(token)


def test_verify_wrong_issuer() -> None:
    with pytest.raises(AuthenticationError):
        _verifier().verify(build_token(issuer="other-issuer"))


def test_verify_wrong_audience() -> None:
    with pytest.raises(AuthenticationError):
        _verifier().verify(build_token(aud="other-audience"))


def test_verify_expired() -> None:
    with pytest.raises(AuthenticationError):
        _verifier().verify(build_token(expired=True))


def test_verify_missing_sub() -> None:
    now = int(time.time())
    token = pyjwt.encode(
        {"tenant_id": "tenant-a", "iss": ISSUER, "aud": AUDIENCE, "exp": now + 3600},
        TEST_SECRET,
        algorithm="HS256",
    )
    with pytest.raises(AuthenticationError):
        _verifier().verify(token)


def test_verify_malformed() -> None:
    with pytest.raises(AuthenticationError):
        _verifier().verify("not-a-token")


# ---- 策略引擎 ----


def test_require_scope_ok() -> None:
    PolicyEngine(DEFAULT_POLICIES).require_scope(_principal(), "tools:call")


def test_require_scope_missing() -> None:
    with pytest.raises(InsufficientScopeError):
        PolicyEngine(DEFAULT_POLICIES).require_scope(_principal(scopes=()), "tools:call")


def test_allow_tool_hit() -> None:
    assert PolicyEngine(DEFAULT_POLICIES).allow_tool(_principal(), "demo", "echo", "call") is True


def test_allow_tool_any_role_hit() -> None:
    principal = _principal(roles=("guest", "analyst"))
    assert PolicyEngine(DEFAULT_POLICIES).allow_tool(principal, "demo", "echo", "call") is True


def test_allow_tool_miss_role() -> None:
    assert PolicyEngine(DEFAULT_POLICIES).allow_tool(_principal(roles=("guest",)), "demo", "echo", "call") is False


def test_allow_tool_miss_tool() -> None:
    assert PolicyEngine(DEFAULT_POLICIES).allow_tool(_principal(), "demo", "other", "call") is False


def test_allow_tool_miss_action() -> None:
    rules = [ToolPolicyRule(tenant="tenant-a", role="analyst", server="demo", tool="echo", actions=["discover"])]
    assert PolicyEngine(rules).allow_tool(_principal(), "demo", "echo", "call") is False


def test_allow_tool_miss_tenant() -> None:
    assert PolicyEngine(DEFAULT_POLICIES).allow_tool(_principal(tenant="other"), "demo", "echo", "call") is False


# ---- Security.from_config ----


def test_security_from_config_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", TEST_SECRET)
    config = GatewayConfig(
        auth=AuthSettings(jwt=JWTSettings(issuer=ISSUER, audience=AUDIENCE, secret_env="JWT_SECRET")),
        policies=DEFAULT_POLICIES,
    )
    security = Security.from_config(config)
    assert security is not None
    principal = security.verify(build_token(roles=["analyst"], scope="tools:list tools:call"))
    assert principal.roles == ("analyst",)


def test_security_from_config_without_auth() -> None:
    assert Security.from_config(GatewayConfig(auth=None)) is None
