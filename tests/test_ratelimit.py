# -*- coding: utf-8 -*-
"""固定窗口限流器单元测试（注入 fakeredis / 假客户端）。"""

from __future__ import annotations

import asyncio

import pytest

import fakeredis.aioredis as fakeredis

from mcp_gateway.errors import RateLimitBackendUnavailableError, RateLimitExceededError
from mcp_gateway.governance.ratelimit import RateLimiter


class _BrokenPipeline:
    """pipeline 的 execute 抛连接异常，模拟 Redis 不可用。"""

    def incr(self, key):
        return self

    def expire(self, key, ttl):
        return self

    async def execute(self):
        raise ConnectionError("redis down")


class _BrokenRedis:
    def pipeline(self, transaction=True):
        return _BrokenPipeline()


def test_within_limit() -> None:
    async def run():
        limiter = RateLimiter(fakeredis.FakeRedis(), "fail_open")
        for _ in range(3):
            await limiter.check("tenant-a", "demo", "echo", window_seconds=60, requests=3)

    asyncio.run(run())


def test_exceeded_raises_429() -> None:
    async def run():
        limiter = RateLimiter(fakeredis.FakeRedis(), "fail_open")
        for _ in range(2):
            await limiter.check("tenant-a", "demo", "echo", window_seconds=60, requests=2)
        with pytest.raises(RateLimitExceededError) as excinfo:
            await limiter.check("tenant-a", "demo", "echo", window_seconds=60, requests=2)
        assert "Retry-After" in excinfo.value.headers

    asyncio.run(run())


def test_key_scoped_by_dimensions() -> None:
    async def run():
        limiter = RateLimiter(fakeredis.FakeRedis(), "fail_open")
        # echo 用满额度后，sleep（不同 tool）不受影响
        await limiter.check("tenant-a", "demo", "echo", window_seconds=60, requests=1)
        await limiter.check("tenant-a", "demo", "sleep", window_seconds=60, requests=1)

    asyncio.run(run())


def test_fail_open_passes() -> None:
    async def run():
        limiter = RateLimiter(_BrokenRedis(), "fail_open")
        await limiter.check("tenant-a", "demo", "echo", window_seconds=60, requests=10)  # 不抛即放行

    asyncio.run(run())


def test_fail_closed_raises_503() -> None:
    async def run():
        limiter = RateLimiter(_BrokenRedis(), "fail_closed")
        with pytest.raises(RateLimitBackendUnavailableError):
            await limiter.check("tenant-a", "demo", "echo", window_seconds=60, requests=10)

    asyncio.run(run())
