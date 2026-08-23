# MCP Gateway（阶段一：纯透传）

基于已验收的 spike 代码实现的 MCP 网关主链路：把多个 MCP 服务器（streamable_http / stdio）聚合为统一 REST API，纯透传工具调用。

## 目录结构

```
configs/gateway.yaml           # 网关配置（servers 列表）
demo_servers/demo_mcp.py       # Demo MCP 服务器（echo + sleep）
src/mcp_gateway/               # 网关实现
  config.py                    # YAML 配置模型
  errors.py                    # 错误与 HTTP 状态码映射
  schemas.py                   # 响应模型
  registry.py                  # 适配器生命周期 + 工具元数据缓存
  service.py                   # 应用服务层（薄封装）
  main.py                      # FastAPI 应用 + REST API
  transports/                  # streamable_http / stdio 适配器
tests/                         # FakeAdapter 单元测试
```

## 安装

```bash
uv pip install -e .
```

## 运行

1. 启动两个 Demo MCP 服务器（另开终端）：

```bash
# streamable-http 版（127.0.0.1:8000/mcp）
.venv/Scripts/python.exe demo_servers/demo_mcp.py --transport streamable-http

# stdio 版（由网关按配置以子进程拉起，无需单独启动）
```

2. 启动网关（127.0.0.1:9000）：

```bash
.venv/Scripts/python.exe -m mcp_gateway.main
# 或
.venv/Scripts/python.exe -m uvicorn mcp_gateway.main:build_default_app --factory --host 127.0.0.1 --port 9000
```

3. 调用 API：

```bash
curl http://127.0.0.1:9000/api/v1/tools
curl -X POST http://127.0.0.1:9000/api/v1/tools/demo-http/echo/call -H "Content-Type: application/json" -d '{"text":"hello"}'
curl -X POST http://127.0.0.1:9000/api/v1/tools/demo-stdio/echo/call -H "Content-Type: application/json" -d '{"text":"hello"}'
```

## 测试

```bash
.venv/Scripts/python.exe -m pytest tests/ -v
```
