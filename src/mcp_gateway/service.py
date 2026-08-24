# -*- coding: utf-8 -*-
"""应用服务层：把注册表能力暴露为 API 可用的操作，并叠加鉴权校验。"""

from __future__ import annotations

from typing import Any

from mcp_gateway.errors import ToolPolicyDeniedError
from mcp_gateway.registry import MCPRegistry
from mcp_gateway.schemas import ToolInfo
from mcp_gateway.security import Principal, Security

# Scope 层常量：接口级能力
SCOPE_LIST = "tools:list"
SCOPE_CALL = "tools:call"
# Tool Policy 层动作：工具级动作
ACTION_DISCOVER = "discover"
ACTION_CALL = "call"


class GatewayService:
    """网关服务：面向 API 的薄封装，叠加两级权限校验。"""

    def __init__(self, registry: MCPRegistry, security: Security | None = None) -> None:
        self._registry = registry
        self._security = security

    def list_tools(self, principal: Principal | None = None) -> list[ToolInfo]:
        """列出工具：按 discover 权限过滤，只返回当前身份可见的工具。"""
        tools = self._registry.list_tools()
        if self._security is None:
            return tools
        self._security.require_scope(principal, SCOPE_LIST)
        return [
            tool
            for tool in tools
            if self._security.allow_tool(principal, tool.server_id, tool.name, ACTION_DISCOVER)
        ]

    async def call_tool(
        self,
        server_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        principal: Principal | None = None,
    ) -> dict[str, Any]:
        """调用工具：同时通过 Scope 与 Tool Policy 校验。"""
        if self._security is not None:
            self._security.require_scope(principal, SCOPE_CALL)
            if not self._security.allow_tool(principal, server_id, tool_name, ACTION_CALL):
                raise ToolPolicyDeniedError()
        return await self._registry.call_tool(server_id, tool_name, arguments)
