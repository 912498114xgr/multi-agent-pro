# R2 步骤级 Trace — 模块说明与用途

> 面试可打开一份真实 Trace，讲清「谁调用了谁、哪步失败、耗时多少」。

## 1. 解决什么问题

| 痛点 | Trace 怎么补 |
|------|----------------|
| WS 只有「开始调用」进度 | 落盘完整时间线（成功+失败+耗时） |
| 子 Agent 内工具主图看不到 | hooks start + format end 经 ContextVar 记账 |
| 任务结束无法回顾 | `trace.json` + `GET .../trace` + 右侧侧拉栏 |

## 2. 核心文件与用途

| 文件 | 用途 |
|------|------|
| [`context/trace.py`](../../context/trace.py) | 协程级收集器：start/end、事件、组装文档 |
| [`context/failure_steps.py`](../../context/failure_steps.py) | R1 失败列表；与 Trace 失败步骤联动 |
| [`observability/trace_io.py`](../../observability/trace_io.py) | 读写 `session/trace.json` |
| [`tools/hooks.py`](../../tools/hooks.py) | 工具入口：`trace_tool_start` |
| [`tools/tool_result.py`](../../tools/tool_result.py) | 工具出口：`trace_tool_end` + 结构化返回 |
| [`agent/mainagent/runner.py`](../../agent/mainagent/runner.py) | init/落盘/`assistant`/`model_result`/`status` |
| [`api/task_store.py`](../../api/task_store.py) | `steps` / `trace_path` 字段 |
| [`api/server.py`](../../api/server.py) | `GET /api/tasks/{id}/trace` |
| [`api/monitor.py`](../../api/monitor.py) | WS 最近 50 条补发（`replay`） |
| 前端 `App.vue` / `client.js` | 右侧「链路 Trace」侧拉栏 |

## 3. 数据流

```text
hooks.report_tool ──► trace_tool_start
format_tool_*     ──► trace_tool_end (+ failure_steps 若失败)
runner astream    ──► trace_event(assistant / model_result)
runner 终态       ──► build_trace_document → write_trace → task_store
前端 finalize     ──► getTaskTrace → 右侧侧拉栏
```

## 4. 如何演示

1. 跑完一题后点右侧「链路 Trace」
2. 或打开 `output/session_<thread_id>/trace.json`
3. 断 MySQL：critical 工具 `status=error` + `duration_ms` 约数秒
4. 断 Tavily、库正常：search `error`，后续写作可为 `ok`，任务 `partial_success`

## 5. 与 Monitor 的分工

- **Monitor/WS**：实时、精简（委派、失败汇总、终态）
- **Trace**：事后、完整（含成功工具与耗时）— 面试讲链路用这个
