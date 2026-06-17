# 05 — `api/monitor.py`：进度监控与 WebSocket

## 这是什么？

Agent 执行过程中的**进度广播中心**。子 Agent 被调用、工具执行、任务完成时，通过 `monitor` 通知控制台和（可选）前端。

## Phase 4 vs Phase 5

| | Phase 4 | Phase 5 |
|---|---------|---------|
| 输出 | 仅 `print [Monitor:xxx]` | 控制台 + WebSocket JSON |
| WebSocket | 接口预留，未实现 | `ConnectionManager` 完整实现 |

## 两个类

### 1. `ToolMonitor`（单例 `monitor`）

业务代码只调这几个方法：

```python
monitor.report_session_dir(path)      # 工作目录已创建
monitor.report_assistant(name, args) # 正在调用子 Agent
monitor.report_tool(name, args)       # 主 Agent 调用工具
monitor.report_task_result(result)    # 最终答案
```

内部 `_emit` 做两件事：

1. 组装 `payload`，尝试通过 WebSocket 发给对应 `thread_id`
2. 控制台打印：`\n[Monitor:{event_type}] {message}`

WebSocket 消息格式：

```json
{
  "type": "monitor_event",
  "event": "assistant_call",
  "message": "正在调用助手: 数据查询助手",
  "data": { "assistant_name": "数据查询助手", "args": {...} },
  "thread_id": "cli-abc123",
  "timestamp": "2026-06-04T10:01:00"
}
```

### 2. `ConnectionManager`（单例 `manager`）

管理 `thread_id → WebSocket` 映射：

```python
await manager.connect(websocket, thread_id)   # 前端连接 /ws/{thread_id}
await manager.send_to_thread(payload, thread_id)  # monitor 推送
manager.disconnect(websocket, thread_id)      # 断开清理
```

## 事件循环问题（重要）

Agent 在 `asyncio.create_task` 里跑，monitor 可能在**同一条事件循环**或**其他线程**里被调用。

```python
if current_loop == manager_loop:
    current_loop.create_task(send_to_thread(...))  # 同循环，直接 create_task
else:
    asyncio.run_coroutine_threadsafe(send_to_thread(...), manager_loop)  # 跨线程
```

这是 FastAPI + 后台任务的经典坑，deep_search_pro 里也有同样逻辑。

## 在项目中的位置

```
runner.py (astream 循环)
    ↓ report_assistant / report_task_result
monitor._emit
    ├──→ print 控制台
    └──→ manager.send_to_thread → 前端 WebSocket

api/server.py
    startup → manager.set_loop
    /ws/{thread_id} → manager.connect
```

## 控制台输出示例

```
[Monitor:session_created] 工作目录已创建: F:/.../output/session_xxx

[Monitor:assistant_call] 正在调用助手: 数据查询助手

[Monitor:task_result] 任务执行完成
```

**不要**在 `_emit` 里再混打 JSON 结构化日志，否则会「格式乱掉」——结构化日志交给 `observability`，monitor 保持人类可读格式。

## 如何验证 WebSocket

1. 启动 `uvicorn api.server:app`
2. 用浏览器插件或 `websocat` 连接 `ws://localhost:8000/ws/your-thread-id`
3. 另开终端 POST `/api/tasks`，同一 `thread_id`
4. WebSocket 应收到 `monitor_event` 消息

## 学习要点

- **观察者模式**：runner 不关心谁在看进度，只调 `monitor`
- **thread_id 是路由键**：ContextVar 取出当前会话 ID，只推给对应连接
- 前端可据此做：步骤条、子 Agent 卡片、最终结果展示区
