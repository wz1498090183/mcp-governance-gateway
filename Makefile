# MCP Governance Gateway 常用命令
# Windows 主机若未安装 make，可直接执行各目标对应的 docker compose / bash 命令。

.PHONY: help up down build test demo config logs

help: ## 显示帮助
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-10s %s\n", $$1, $$2}'

up: ## 构建镜像并后台启动全部服务
	docker compose up -d --build

down: ## 停止并移除容器与网络
	docker compose down

build: ## 仅构建镜像
	docker compose build

test: ## 运行单元测试（本机解释器）
	python -m pytest -q

demo: up ## 一键演示：启动后运行完整场景断言
	bash scripts/demo.sh

config: ## 校验 compose 配置
	docker compose config

logs: ## 查看服务日志
	docker compose logs -f
