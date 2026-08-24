# -*- coding: utf-8 -*-
"""治理门面：组合限流、工具超时解析与审计，对 Service 层提供统一入口。"""

from __future__ import annotations

import os

import redis.asyncio as redis

from mcp_gateway.config import GatewayConfig, ToolGovernanceRule
from mcp_gateway.governance.audit import AuditLogger
from mcp_gateway.governance.ratelimit import RateLimiter


class Governance:
    """治理门面：tool_timeout_ms 解析超时、check_rate_limit 限流、audit 审计。"""

    def __init__(
        self,
        default_timeout_ms: int,
        rules: list[ToolGovernanceRule],
        rate_limiter: RateLimiter | None,
        audit_logger: AuditLogger,
    ) -> None:
        self._default_timeout_ms = default_timeout_ms
        self._rule_map = {(rule.server, rule.tool): rule for rule in rules}
        self._rate_limiter = rate_limiter
        self._audit = audit_logger

    @classmethod
    def from_config(cls, config: GatewayConfig) -> Governance:
        """从网关配置构建治理门面。

        仅当存在启用了限流的工具规则时才构建 Redis 客户端并校验 REDIS_URL。
        """
        rules = config.tool_governance
        needs_redis = any(r.rate_limit is not None and r.rate_limit.enabled for r in rules)
        rate_limiter = None
        if needs_redis:
            url = os.environ.get(config.redis.url_env)
            if not url:
                raise RuntimeError(f"缺少环境变量 {config.redis.url_env}，无法启用限流")
            rate_limiter = RateLimiter(redis.from_url(url), config.gateway.redis_failure_mode)
        return cls(config.gateway.default_timeout_ms, rules, rate_limiter, AuditLogger())

    def tool_timeout_ms(self, server: str, tool: str) -> int:
        """解析工具调用超时：逐工具覆盖 → 全局默认。"""
        rule = self._rule_map.get((server, tool))
        if rule is not None and rule.timeout_ms is not None:
            return rule.timeout_ms
        return self._default_timeout_ms

    def rate_limit_failure_mode(self) -> str | None:
        """返回限流后端 failure_mode；未启用限流时返回 None（供就绪探针使用）。"""
        if self._rate_limiter is None:
            return None
        return self._rate_limiter.failure_mode

    async def redis_ready(self) -> bool:
        """Redis 就绪探测：未启用限流或 fail_open 恒 True，fail_closed 实际 ping。"""
        if self._rate_limiter is None:
            return True
        return await self._rate_limiter.ping()

    async def check_rate_limit(self, tenant: str, server: str, tool: str) -> None:
        """执行限流；工具未配置限流规则时跳过。"""
        if self._rate_limiter is None:
            return
        rule = self._rule_map.get((server, tool))
        if rule is None or rule.rate_limit is None or not rule.rate_limit.enabled:
            return
        await self._rate_limiter.check(
            tenant, server, tool, rule.rate_limit.window_seconds, rule.rate_limit.requests
        )

    def audit(self, **fields) -> None:
        self._audit.log(**fields)

    async def aclose(self) -> None:
        """关闭治理资源（Redis 客户端）。"""
        if self._rate_limiter is not None:
            await self._rate_limiter.aclose()
