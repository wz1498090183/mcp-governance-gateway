# -*- coding: utf-8 -*-
"""应用服务层：把注册表能力暴露为 API 可用的操作，并叠加鉴权与治理。"""

from __future__ import annotations

import time
from typing import Any

from mcp_gateway.errors import (
    AdapterUnavailableError,
    GatewayError,
    InsufficientScopeError,
    RateLimitBackendUnavailableError,
    RateLimitExceededError,
    ToolPolicyDeniedError,
    ToolTimeoutError,
)
from mcp_gateway.governance import Governance
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
    """网关服务：面向 API 的薄封装，叠加鉴权、限流、超时与审计。"""

    def __init__(
        self,
        registry: MCPRegistry,
        security: Security | None = None,
        governance: Governance | None = None,
    ) -> None:
        self._registry = registry
        self._security = security
        self._governance = governance

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
        """调用工具：鉴权 → 限流 → 超时 → 调用，finally 统一落审计。"""
        tenant = principal.tenant_id if principal else ""
        subject = principal.sub if principal else ""
        policy_decision = "allow"
        status = "success"
        error_code = ""
        param_keys = sorted((arguments or {}).keys())
        start = time.perf_counter()

        try:
            if self._security is not None:
                self._security.require_scope(principal, SCOPE_CALL)
                if not self._security.allow_tool(principal, server_id, tool_name, ACTION_CALL):
                    raise ToolPolicyDeniedError()

            timeout_seconds = None
            if self._governance is not None:
                await self._governance.check_rate_limit(tenant, server_id, tool_name)
                timeout_ms = self._governance.tool_timeout_ms(server_id, tool_name)
                if timeout_ms and timeout_ms > 0:
                    timeout_seconds = timeout_ms / 1000.0

            return await self._registry.call_tool(server_id, tool_name, arguments, timeout_seconds)
        except (InsufficientScopeError, ToolPolicyDeniedError) as exc:
            policy_decision = "deny"
            status = "denied"
            error_code = exc.code
            raise
        except (RateLimitExceededError, RateLimitBackendUnavailableError) as exc:
            status = "rate_limited"
            error_code = exc.code
            raise
        except ToolTimeoutError as exc:
            status = "timeout"
            error_code = exc.code
            raise
        except AdapterUnavailableError as exc:
            status = "error"
            error_code = exc.code
            raise
        except GatewayError as exc:
            status = "error"
            error_code = exc.code
            raise
        finally:
            if self._governance is not None:
                self._governance.audit(
                    event="tool.call",
                    tenant=tenant,
                    subject=subject,
                    server_id=server_id,
                    tool_name=tool_name,
                    policy_decision=policy_decision,
                    status=status,
                    latency_ms=int((time.perf_counter() - start) * 1000),
                    error_code=error_code,
                    param_keys=param_keys,
                )
