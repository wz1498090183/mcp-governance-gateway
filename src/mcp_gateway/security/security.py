# -*- coding: utf-8 -*-
"""鉴权门面：组合 JWT 验证器与策略引擎，对 Service / API 层提供统一入口。"""

from __future__ import annotations

import os

from mcp_gateway.config import GatewayConfig
from mcp_gateway.security.policy import PolicyEngine
from mcp_gateway.security.verifier import HS256TokenVerifier, Principal


class Security:
    """鉴权门面：verify 认证，require_scope / allow_tool 鉴权。"""

    def __init__(self, verifier: HS256TokenVerifier, policy: PolicyEngine) -> None:
        self._verifier = verifier
        self._policy = policy

    @classmethod
    def from_config(cls, config: GatewayConfig) -> Security | None:
        """从网关配置构建安全门面；未配置 auth 时返回 None（纯透传模式）。"""
        if config.auth is None:
            return None
        secret = os.environ.get(config.auth.jwt.secret_env)
        if not secret:
            raise RuntimeError(f"缺少环境变量 {config.auth.jwt.secret_env}，无法启动鉴权")
        verifier = HS256TokenVerifier(
            secret=secret,
            issuer=config.auth.jwt.issuer,
            audience=config.auth.jwt.audience,
            algorithm=config.auth.jwt.algorithm,
        )
        policy = PolicyEngine(config.policies)
        return cls(verifier, policy)

    def verify(self, token: str) -> Principal:
        return self._verifier.verify(token)

    def require_scope(self, principal: Principal, scope: str) -> None:
        self._policy.require_scope(principal, scope)

    def allow_tool(self, principal: Principal, server: str, tool: str, action: str) -> bool:
        return self._policy.allow_tool(principal, server, tool, action)
