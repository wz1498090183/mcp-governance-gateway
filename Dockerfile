# MCP Governance Gateway 镜像（v0.1，单阶段，不做多阶段/压缩优化）
# 基础镜像固定 python:3.12-slim；mcp 2.0.0 要求 Python >=3.10，源码仅用 3.10+ 语法。
FROM python:3.12-slim

# 设置工作目录（后续 COPY 与 stdio 子进程均以此为基准）
WORKDIR /app

# 先安装依赖，充分利用 Docker 层缓存
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 拷贝源码、Demo 服务器与配置
COPY src/ ./src/
COPY demo_servers/ ./demo_servers/
COPY configs/ ./configs/

# 源码经 PYTHONPATH 导入，不执行 pip install .（避开本地 pyproject 的 requires-python >=3.14 约束）
ENV PYTHONPATH=/app/src
# 固定使用容器专用 demo 配置（demo-http 跨容器地址 + 限流开启 + stdio 绝对路径）
ENV GATEWAY_CONFIG_PATH=/app/configs/gateway.demo.yaml

EXPOSE 9000

# build_default_app 为工厂函数，需 --factory；绑定 0.0.0.0 供宿主机与其他容器访问
CMD ["uvicorn", "mcp_gateway.main:build_default_app", "--factory", "--host", "0.0.0.0", "--port", "9000"]
