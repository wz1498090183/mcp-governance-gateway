# -*- coding: utf-8 -*-
"""结构化审计日志：JSON Formatter 输出到 stdout。

严格白名单序列化，绝不记录 JWT / Secret / 参数值 / 工具返回内容。
"""

from __future__ import annotations

import json
import logging
import sys
import uuid
from contextvars import ContextVar

# 单次请求的 trace_id，由中间件写入、审计日志读取
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="-")

# 审计字段白名单
_AUDIT_FIELDS = (
    "event",
    "trace_id",
    "tenant",
    "subject",
    "server_id",
    "tool_name",
    "policy_decision",
    "status",
    "latency_ms",
    "error_code",
    "param_keys",
)

_LOGGER_NAME = "mcp_gateway.audit"


def new_trace_id() -> str:
    """生成新的 trace_id（32 位 hex）。"""
    return uuid.uuid4().hex


class JsonFormatter(logging.Formatter):
    """把审计记录序列化为单行 JSON，仅输出白名单字段。"""

    def format(self, record: logging.LogRecord) -> str:
        data = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
        }
        for field in _AUDIT_FIELDS:
            data[field] = getattr(record, field, None)
        return json.dumps(data, ensure_ascii=False, default=str)


class AuditLogger:
    """审计日志写入器：emit 结构化字段，不含任何敏感信息。"""

    def __init__(self, logger_name: str = _LOGGER_NAME) -> None:
        self._logger = logging.getLogger(logger_name)

    def log(
        self,
        *,
        event: str,
        tenant: str = "",
        subject: str = "",
        server_id: str = "",
        tool_name: str = "",
        policy_decision: str = "",
        status: str = "",
        latency_ms: int = 0,
        error_code: str = "",
        param_keys: list[str] | None = None,
        trace_id: str | None = None,
    ) -> None:
        """落一条审计日志（字段白名单见 _AUDIT_FIELDS）。"""
        extra = {
            "event": event,
            "trace_id": trace_id or trace_id_var.get(),
            "tenant": tenant,
            "subject": subject,
            "server_id": server_id,
            "tool_name": tool_name,
            "policy_decision": policy_decision,
            "status": status,
            "latency_ms": latency_ms,
            "error_code": error_code,
            "param_keys": param_keys or [],
        }
        self._logger.info("audit", extra=extra)


def setup_audit_logging(level: int = logging.INFO) -> None:
    """配置审计 logger：stdout 输出 JSON，不向上传播。幂等。"""
    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(level)
    logger.propagate = False
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger.handlers = [handler]
