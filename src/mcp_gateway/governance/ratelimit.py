# -*- coding: utf-8 -*-
"""固定窗口限流（Redis 实现）。

key：rl:{tenant}:{server}:{tool}:{bucket}，用事务管道（MULTI/EXEC）执行
INCR + EXPIRE（过期时间为窗口 2 倍）。禁止裸 INCR + EXPIRE 两条独立命令。
Redis 故障时按全局 failure_mode：fail_open 放行，fail_closed 返回 503。
"""

from __future__ import annotations

import logging
import time

from mcp_gateway.errors import RateLimitBackendUnavailableError, RateLimitExceededError

logger = logging.getLogger(__name__)


class RateLimiter:
    """固定窗口限流器：持有 Redis 异步客户端，不关心连接配置。"""

    def __init__(self, client, failure_mode: str) -> None:
        self._client = client
        self._failure_mode = failure_mode

    async def check(self, tenant: str, server: str, tool: str, window_seconds: int, requests: int) -> None:
        """对一次工具调用执行限流判定，超限抛 429。"""
        try:
            bucket = int(time.time() // window_seconds)
            key = f"rl:{tenant}:{server}:{tool}:{bucket}"
            pipe = self._client.pipeline(transaction=True)  # MULTI/EXEC
            pipe.incr(key)
            pipe.expire(key, window_seconds * 2)
            count = int((await pipe.execute())[0])
            if count > requests:
                retry_after = window_seconds - int(time.time() % window_seconds)
                raise RateLimitExceededError(retry_after)
        except RateLimitExceededError:
            raise
        except Exception as exc:
            if self._failure_mode == "fail_closed":
                raise RateLimitBackendUnavailableError() from exc
            logger.warning("限流后端不可用，fail_open 放行: %s", exc)

    async def aclose(self) -> None:
        """关闭 Redis 客户端。"""
        try:
            await self._client.aclose()
        except Exception:
            logger.warning("关闭 Redis 客户端失败（忽略）")
