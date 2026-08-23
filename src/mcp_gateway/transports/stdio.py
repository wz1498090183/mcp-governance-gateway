# -*- coding: utf-8 -*-
"""stdio 传输适配器：管理 MCP 子进程完整生命周期。"""

from __future__ import annotations

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from mcp_gateway.transports.base import _BaseAdapter


class StdioAdapter(_BaseAdapter):
    """基于 MCP SDK 原生 stdio_client 的适配器。

    启动命令与参数从配置数组直传 StdioServerParameters（无 shell、无字符串拼接）。
    close() 时退出 stdio_client 上下文，由 SDK 负责终止并回收子进程。
    """

    def __init__(
        self,
        server_id: str,
        command: str,
        args: list[str],
        timeout_seconds: float | None,
    ) -> None:
        super().__init__(server_id, timeout_seconds)
        self._command = command
        self._args = args

    async def _open(self) -> ClientSession:
        """以子进程方式启动服务器并完成握手。"""
        params = StdioServerParameters(command=self._command, args=self._args)
        read, write = await self._stack.enter_async_context(stdio_client(params))
        session = await self._stack.enter_async_context(
            ClientSession(read, write, read_timeout_seconds=self._timeout_seconds)
        )
        await session.initialize()
        return session
