# -*- coding: utf-8 -*-
"""MCP 注册表：适配器生命周期管理与工具元数据缓存。

只负责「映射 + 生命周期」，不掺杂业务逻辑。
"""

from __future__ import annotations

import logging
from typing import Any

from mcp import types
from mcp.shared.exceptions import MCPError

from mcp_gateway.config import GatewayConfig
from mcp_gateway.errors import AdapterUnavailableError, ServerNotFoundError, ToolNotFoundError, ToolTimeoutError
from mcp_gateway.schemas import ToolInfo
from mcp_gateway.transports import MCPTransportAdapter, create_adapter

logger = logging.getLogger(__name__)


class MCPRegistry:
    """维护 MCP 服务器适配器的映射与生命周期，缓存工具元数据。"""

    def __init__(
        self,
        adapters: dict[str, MCPTransportAdapter],
        required: dict[str, bool] | None = None,
    ) -> None:
        self._adapters = adapters
        self._required = required or {}
        self._tools: dict[str, dict[str, types.Tool]] = {}

    @classmethod
    def from_config(cls, config: GatewayConfig) -> MCPRegistry:
        """根据配置创建适配器映射。"""
        timeout_ms = config.gateway.default_timeout_ms
        timeout_seconds = timeout_ms / 1000.0 if timeout_ms > 0 else None

        adapters: dict[str, MCPTransportAdapter] = {}
        required: dict[str, bool] = {}
        for server in config.servers:
            if not server.enabled:
                continue
            adapters[server.id] = create_adapter(server, timeout_seconds)
            required[server.id] = server.required
        return cls(adapters, required)

    async def initialize(self) -> None:
        """统一初始化所有适配器并缓存工具元数据。

        任一服务器初始化失败仅记录日志并关闭该适配器，不再抛出——进程保持存活，
        业务可用性由 readiness() / /ready 端点反映（required 服务器失败时返回 503）。
        """
        for server_id in self._adapters:
            try:
                await self._init_one(server_id)
            except Exception as exc:
                logger.warning(
                    "服务器 %s 初始化失败（required=%s）: %s",
                    server_id, self._required.get(server_id, False), exc,
                )
                await self._adapters[server_id].close()

    async def _init_one(self, server_id: str) -> None:
        """初始化单个适配器并缓存其工具列表。"""
        adapter = self._adapters[server_id]
        await adapter.initialize()
        tools = await adapter.list_tools()
        self._tools[server_id] = {tool.name: tool for tool in tools}

    def readiness(self) -> dict[str, dict[str, bool]]:
        """返回每个服务器的就绪状态（required 标志 + 是否已缓存工具），供 /ready 使用。"""
        return {
            server_id: {
                "required": self._required.get(server_id, False),
                "ready": server_id in self._tools,
            }
            for server_id in self._adapters
        }

    async def close(self) -> None:
        """逐个关闭适配器。"""
        for adapter in self._adapters.values():
            await adapter.close()
        self._tools.clear()

    def list_tools(self) -> list[ToolInfo]:
        """返回所有已注册工具（含所属 server_id）。"""
        result: list[ToolInfo] = []
        for server_id, tools in self._tools.items():
            for tool in tools.values():
                result.append(
                    ToolInfo(
                        server_id=server_id,
                        name=tool.name,
                        description=tool.description,
                        input_schema=tool.input_schema or {},
                    )
                )
        return result

    async def call_tool(
        self,
        server_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        """调用指定服务器的工具，透传参数并返回原始结果。"""
        if server_id not in self._adapters:
            raise ServerNotFoundError(f"服务器不存在: {server_id}")

        try:
            if server_id not in self._tools:
                await self._init_one(server_id)
            tools = self._tools.get(server_id, {})
            if tool_name not in tools:
                raise ToolNotFoundError(f"工具不存在: {server_id}/{tool_name}")
            result = await self._adapters[server_id].call_tool(tool_name, arguments, timeout_seconds)
        except (ServerNotFoundError, ToolNotFoundError):
            raise
        except MCPError as exc:
            # 工具调用超时：SDK 把读超时转为 REQUEST_TIMEOUT，适配器 worker 已关闭连接
            if exc.code == types.REQUEST_TIMEOUT:
                raise ToolTimeoutError() from exc
            logger.warning("调用工具失败 %s/%s: %s", server_id, tool_name, exc)
            raise AdapterUnavailableError(f"调用失败: {server_id}/{tool_name}") from exc
        except Exception as exc:
            logger.warning("调用工具失败 %s/%s: %s", server_id, tool_name, exc)
            raise AdapterUnavailableError(f"调用失败: {server_id}/{tool_name}") from exc

        return result.model_dump(mode="json")
