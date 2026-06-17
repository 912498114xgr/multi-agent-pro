# Phase 5 模块文档索引

每个新增/改造模块一篇独立说明，建议按编号顺序阅读。

| 序号 | 文件 | 模块 | 一句话 |
|------|------|------|--------|
| 01 | [01-llm-model.md](01-llm-model.md) | `llm/model.py` | 让大模型 API 连得稳 |
| 02 | [02-config-扩展.md](02-config-扩展.md) | `config/settings.py` | 超时与调试开关 |
| 03 | [03-task-store.md](03-task-store.md) | `api/task_store.py` | 任务状态机 |
| 04 | [04-api-server.md](04-api-server.md) | `api/server.py` | HTTP 服务入口 |
| 05 | [05-monitor-websocket.md](05-monitor-websocket.md) | `api/monitor.py` | 实时进度推送 |
| 06 | [06-observability.md](06-observability.md) | `observability/logging.py` | JSON 结构化日志 |
| 07 | [07-runner-改造.md](07-runner-改造.md) | `agent/mainagent/runner.py` | 串联所有新增能力 |

总览：[../Phase5-新增模块学习指南.md](../Phase5-新增模块学习指南.md)

**精读代码**：使用 `@learn-before-implement`（通用 Skill，默认方法级）；本仓库路径与分段见 [project-overlay.md](../../.cursor/skills/learn-before-implement/project-overlay.md)。
