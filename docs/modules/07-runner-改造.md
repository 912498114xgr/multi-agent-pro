# 07 — `agent/mainagent/runner.py` 改造说明

## 这是什么？

主 Agent 的**执行引擎**（Phase 4 已有）。Phase 5 没有重写 Agent 逻辑，而是让它能接入 **任务状态、调试开关、结构化错误日志**。

## 改造点对照

| 改造 | 代码 | 作用 |
|------|------|------|
| 对接 task_store | `create` / `mark_running` / `mark_done` / `mark_error` | API 可查询任务状态 |
| 调试开关 | `_dbg()` | `RUNNER_DEBUG=1` 才打印 chunk |
| 结构化日志 | `_log()` / `log_error()` | debug 模式或异常时写 JSON |
| 工具上报 | `monitor.report_tool` | 主 Agent 直调工具时也推送 |
| 结束提示 | `[Runner] 结束 session_id=...` | 明确执行边界 |

## 执行流程（改造后）

```
run_deep_agent(query, session_id)
│
├─ task_store.create（若 CLI 直连且尚无记录）
├─ task_store.mark_running
├─ _prepare_session → 创建 output 目录、复制上传文件
├─ setup_request_context → ContextVar（session_dir, thread_id, trace_id）
├─ monitor.report_session_dir
│
├─ main_agent.astream(...)  循环
│   ├─ node=model + tool_calls + name=task → monitor.report_assistant
│   ├─ node=model + tool_calls + 其他工具 → monitor.report_tool
│   └─ node=model + content → monitor.report_task_result
│
├─ task_store.mark_done（或 mark_error）
└─ reset_all_tokens
```

## 调试函数

```python
def _dbg(*args):
    if _settings.runner_debug:
        print(*args)

def _log(event, message="", **extra):
    if _settings.runner_debug:
        log_info(_logger, event, message, **extra)
```

- **默认**：只看到 `当前会话的main_agent开始执行了`、Monitor 行、最终结果预览
- **DEBUG=1**：额外看到每个 chunk 的 state、messages、tool_call 详情

## 与 API 层如何配合

```
server._start_task
    → task_store.create
    → asyncio.create_task(run_deep_agent)

run_deep_agent
    → mark_running ... mark_done
    → monitor → WebSocket
```

同一份 `run_deep_agent` 同时服务 **CLI** 和 **HTTP**，没有两套逻辑。

## 没改什么？（故意保持）

- `create_deep_agent` 组装方式
- 5 个子 Agent 列表
- astream 解析 model/tools 节点的核心逻辑
- `_prepare_session` / `_build_path_instruction`

**原则**：外壳（API、store、monitor）可换，Agent 内核稳定。

## 学习要点

1. **单一执行入口**：无论从哪里调用，都走 `run_deep_agent`
2. **finally 里 reset ContextVar**：防止下一个协程「串台」
3. **final_result 跟踪**：只有 model 节点返回 content 才算最终答案；中间子 Agent 结果是 tool message

## 推荐阅读顺序

1. 先跑通 `python agent/test_run.py`
2. 再读 [03-task-store.md](03-task-store.md) + [05-monitor-websocket.md](05-monitor-websocket.md)
3. 最后启动 server，用 curl + WebSocket 观察同一条链路
