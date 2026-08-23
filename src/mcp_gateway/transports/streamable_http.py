# -*- coding: utf-8 -*-
"""Streamable HTTP 传输适配器：全局复用一条 HTTP 连接。"""

from __future__ import annotations

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from mcp_gateway.transports.base import _BaseAdapter


class StreamableHTTPAdapter(_BaseAdapter):
    """基于 MCP SDK 原生 streamable_http_client 的适配器。

    连接在 initialize 时建立，后续调用复用同一条会话，直到 close() 或失效后重建。
    """

    def __init__(self, server_id: str, endpoint: str, timeout_seconds: float | None) -> None:
        super().__init__(server_id, timeout_seconds)
        self._endpoint = endpoint

    async def _open(self) -> ClientSession:
        """进入 streamable_http_client 上下文并完成握手。"""
        read, write = await self._stack.enter_async_context(streamable_http_client(self._endpoint))
        session = await self._stack.enter_async_context(
            ClientSession(read, write, read_timeout_seconds=self._timeout_seconds)
        )
        await session.initialize()
        return session
