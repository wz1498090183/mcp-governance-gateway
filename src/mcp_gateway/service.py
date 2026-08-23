# -*- coding: utf-8 -*-
"""应用服务层：把注册表能力暴露为 API 可用的操作（阶段一为纯透传）。"""

from __future__ import annotations

from typing import Any

from mcp_gateway.registry import MCPRegistry
from mcp_gateway.schemas import ToolInfo


class GatewayService:
    """网关服务：面向 API 的薄封装。"""

    def __init__(self, registry: MCPRegistry) -> None:
        self._registry = registry

    def list_tools(self) -> list[ToolInfo]:
        return self._registry.list_tools()

    async def call_tool(self, server_id: str, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return await self._registry.call_tool(server_id, tool_name, arguments)
