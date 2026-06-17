# 06 — `observability/logging.py`：结构化日志

## 这是什么？

可选的 **JSON 格式日志**模块，自动附带 `trace_id` 和 `thread_id`，方便日后对接 ELK、Loki 等日志系统。

## 为什么单独做一层？

| 方式 | 优点 | 缺点 |
|------|------|------|
| `print` | 简单直观 | 难以检索、无法关联请求 |
| `[Monitor:xxx]` | 给人看进度 | 不适合机器解析 |
| JSON 日志 | 可检索、可告警 | 控制台可读性差 |

三者**分工不同**，不应混在 `monitor._emit` 里。

## 输出长什么样？

```json
{"event": "agent_error", "message": "Connection error", "trace_id": "a1b2-...", "thread_id": "cli-xxx", "session_id": "cli-xxx"}
```

## 主要 API

```python
from observability.logging import get_logger, log_info, log_error

logger = get_logger("runner")
log_info(logger, "agent_start", "查询缺陷", session_id="xxx")
log_error(logger, "agent_error", str(e), session_id="xxx")
```

`trace_id` / `thread_id` 从 `context/session.py` 的 ContextVar 自动读取——前提是 `setup_request_context` 已执行。

## 什么时候会打印？

| 场景 | 是否输出 JSON |
|------|----------------|
| 正常运行 | **否**（避免和 Monitor 混在一起） |
| `RUNNER_DEBUG=1` | runner 的 `_log()` 会写 JSON |
| 异常 `log_error` | **是**（异常需要留痕） |

## 在项目中的位置

```
context/session.py  (trace_id, thread_id)
        ↓
observability/logging.py
        ↓
agent/mainagent/runner.py  (异常时 log_error)
```

`monitor.py` **不依赖**本模块，保持控制台格式干净。

## 学习要点

- **可观测性三件套**：日志（本模块）、指标（未做）、链路追踪（trace_id 已预留）
- MVP 只做最小 JSON 日志；生产环境通常输出到文件或 stdout 由采集器抓取
- `get_logger("efficiency_agent.runner")` 是标准 logging 层次命名

## V2 可扩展方向

- 写入 `logs/app.jsonl` 文件
- 与 OpenTelemetry 集成
- 按 `trace_id` 串联一次请求的所有 log 行
