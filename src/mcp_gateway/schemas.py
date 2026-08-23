# -*- coding: utf-8 -*-
"""API 响应模型（最小）。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ToolInfo(BaseModel):
    """工具元数据，含所属 server_id。"""

    server_id: str
    name: str
    description: str | None = None
    input_schema: dict[str, Any] = Field(default_factory=dict)
