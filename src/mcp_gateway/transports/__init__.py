# -*- coding: utf-8 -*-
"""传输适配器工厂：根据配置的 transport 字段创建对应适配器。"""

from __future__ import annotations

from mcp_gateway.config import ServerConfig
from mcp_gateway.transports.base import MCPTransportAdapter
from mcp_gateway.transports.stdio import StdioAdapter
from mcp_gateway.transports.streamable_http import StreamableHTTPAdapter

__all__ = [
    "MCPTransportAdapter",
    "StreamableHTTPAdapter",
    "StdioAdapter",
    "create_adapter",
]


def create_adapter(server: ServerConfig, timeout_seconds: float | None) -> MCPTransportAdapter:
    """根据 server 配置创建传输适配器。

    transport 取值与 YAML 字段一致：``streamable_http`` 或 ``stdio``。
    """
    if server.transport == "streamable_http":
        return StreamableHTTPAdapter(server.id, server.endpoint, timeout_seconds)
    if server.transport == "stdio":
        return StdioAdapter(server.id, server.command, server.args, timeout_seconds)
    raise ValueError(f"不支持的 transport: {server.transport}")
