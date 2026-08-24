# -*- coding: utf-8 -*-
"""网关错误定义，映射到 HTTP 状态码与稳定错误码。"""

from __future__ import annotations


class GatewayError(Exception):
    """网关错误基类：status_code 为 HTTP 状态码，code 为稳定错误码，headers 为可选响应头。"""

    status_code: int = 500
    code: str = "INTERNAL_ERROR"

    def __init__(self, message: str, headers: dict[str, str] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.headers = headers


class ServerNotFoundError(GatewayError):
    """server_id 不存在。"""

    status_code = 404
    code = "SERVER_NOT_FOUND"


class ToolNotFoundError(GatewayError):
    """工具不存在。"""

    status_code = 404
    code = "TOOL_NOT_FOUND"


class AdapterUnavailableError(GatewayError):
    """传输适配器不可用（调用超时、传输错误、协议解析失败等）。"""

    status_code = 502
    code = "ADAPTER_UNAVAILABLE"


class AuthenticationError(GatewayError):
    """认证失败（401）：Token 缺失/非法/过期/签名错误/受众错误等，统一模糊返回。"""

    status_code = 401
    code = "AUTH_INVALID_TOKEN"

    def __init__(self) -> None:
        super().__init__("认证失败")


class InsufficientScopeError(GatewayError):
    """缺少所需 Scope（403）。"""

    status_code = 403
    code = "AUTH_INSUFFICIENT_SCOPE"

    def __init__(self) -> None:
        super().__init__("权限不足")


class ToolPolicyDeniedError(GatewayError):
    """工具策略未命中（403）。"""

    status_code = 403
    code = "POLICY_TOOL_DENIED"

    def __init__(self) -> None:
        super().__init__("权限不足")


class RateLimitExceededError(GatewayError):
    """触发限流（429），响应头携带 Retry-After。"""

    status_code = 429
    code = "RATE_LIMIT_EXCEEDED"

    def __init__(self, retry_after: int) -> None:
        super().__init__("请求过于频繁", headers={"Retry-After": str(retry_after)})


class RateLimitBackendUnavailableError(GatewayError):
    """限流后端不可用（503，仅 fail_closed 模式）。"""

    status_code = 503
    code = "RATE_LIMIT_BACKEND_UNAVAILABLE"

    def __init__(self) -> None:
        super().__init__("限流服务不可用")


class ToolTimeoutError(GatewayError):
    """工具调用超时（504）。"""

    status_code = 504
    code = "TOOL_TIMEOUT"

    def __init__(self) -> None:
        super().__init__("工具调用超时")
