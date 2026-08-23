# -*- coding: utf-8 -*-
"""网关错误定义，映射到 HTTP 状态码。"""

from __future__ import annotations


class GatewayError(Exception):
    """网关错误基类。"""

    status_code: int = 500

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ServerNotFoundError(GatewayError):
    """server_id 不存在。"""

    status_code = 404


class ToolNotFoundError(GatewayError):
    """工具不存在。"""

    status_code = 404


class AdapterUnavailableError(GatewayError):
    """传输适配器不可用（调用超时、传输错误、协议解析失败等）。"""

    status_code = 502
