# -*- coding: utf-8 -*-
"""两级权限校验：Scope 层（接口级能力）+ Tool Policy 层（工具级动作）。

Scope 来自 Token 的 scope claim，Policy 来自配置文件，二者严格分层、互不合并。
策略匹配为五维精确匹配：tenant + role + server + tool + action。
任一角色命中即允许，未命中默认拒绝；不实现 Deny / 通配符 / 权限继承。
"""

from __future__ import annotations

from mcp_gateway.config import ToolPolicyRule
from mcp_gateway.errors import InsufficientScopeError
from mcp_gateway.security.verifier import Principal


class PolicyEngine:
    """工具权限策略引擎。"""

    def __init__(self, rules: list[ToolPolicyRule]) -> None:
        # (tenant, role, server, tool) -> 允许的动作集合
        self._allow: dict[tuple[str, str, str, str], set[str]] = {}
        for rule in rules:
            key = (rule.tenant, rule.role, rule.server, rule.tool)
            self._allow.setdefault(key, set()).update(rule.actions)

    def require_scope(self, principal: Principal, scope: str) -> None:
        """Scope 层校验：缺失即抛 403。"""
        if scope not in principal.scopes:
            raise InsufficientScopeError()

    def allow_tool(self, principal: Principal, server: str, tool: str, action: str) -> bool:
        """Tool Policy 层校验：任一角色命中允许即返回 True，否则 False。"""
        for role in principal.roles:
            key = (principal.tenant_id, role, server, tool)
            if action in self._allow.get(key, ()):
                return True
        return False
