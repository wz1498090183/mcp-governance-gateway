# -*- coding: utf-8 -*-
"""测试用 Fake 适配器：实现 MCPTransportAdapter 协议。"""

from __future__ import annotations

from typing import Any

from mcp import types


class FakeAdapter:
    """内存中的假适配器，用于 API 单元测试，不启动真实 MCP 服务器。"""

    def __init__(self, server_id: str, tool_names: list[str], fail_calls: bool = False) -> None:
        self._server_id = server_id
        self._tool_names = tool_names
        self._fail_calls = fail_calls
        self.initialized = False
        self.closed = False

    @property
    def server_id(self) -> str:
        return self._server_id

    async def initialize(self) -> None:
        self.initialized = True

    async def list_tools(self) -> list[types.Tool]:
        return [
            types.Tool(
                name=name,
                description=f"{name} 工具",
                input_schema={"type": "object", "properties": {}},
            )
            for name in self._tool_names
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> types.CallToolResult:
        if self._fail_calls:
            raise RuntimeError("fake 传输错误")
        text = arguments.get("text", "")
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=f"{name}:{text}")],
            is_error=False,
        )

    async def close(self) -> None:
        self.closed = True
