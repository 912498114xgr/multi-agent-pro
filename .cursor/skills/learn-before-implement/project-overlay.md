# 项目补充（multi-agent-pro / EfficiencyAgent）

> **可选 overlay**：仅在当前仓库使用 `@learn-before-implement` 时，Agent 读完通用 [SKILL.md](SKILL.md) 后可参考本文。其他仓库可忽略或自建同名文件。

## 文档索引

| 文档 | 用途 |
|------|------|
| `docs/Phase5-新增模块学习指南.md` | Phase 5 总览与序列图 |
| `docs/modules/README.md` | 各模块索引 |
| `docs/agent执行过程梳理.md` | 执行过程 |

## 关键代码路径

```
agent/test_run.py          CLI 入口
agent/mainagent/runner.py  主 Agent 执行
api/server.py              FastAPI
api/task_store.py          任务状态
api/monitor.py             进度 + WebSocket
llm/model.py               LLM 连接
context/session.py         ContextVar
```

## 建议逻辑分段（本仓库）

### api/monitor.py

| 块 | 内容 |
|----|------|
| ToolMonitor 单例 | `__new__`、`set_websocket_manager` |
| _emit | payload、跨协程发 WS |
| report_* | 四个上报入口 |
| ConnectionManager | connect / disconnect / send_to_thread |

### api/task_store.py

| 块 | 内容 |
|----|------|
| TaskStatus + __init__ | 状态机、`threading.Lock` |
| create / get | 建单与查询 |
| _update + mark_* | 状态变迁 |

### api/server.py

| 块 | 内容 |
|----|------|
| 初始化 + CORS | app、目录 |
| 任务提交 | `_start_task`、`create_task` |
| GET / 上传 / 下载 | 辅助 API |
| WebSocket | `/ws/{thread_id}` |

## 参考同构项目

`../deep_search_pro/api/server.py`、`monitor.py` — API 层结构类似，业务不同。

## 本地命令

```bash
.\.venv\Scripts\python.exe agent\test_run.py
uvicorn api.server:app --reload --port 8000
```
