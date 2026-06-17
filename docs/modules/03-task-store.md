# 03 — `api/task_store.py`：任务状态存储

## 这是什么？

内存里的**任务状态机**。每个 `thread_id` 对应一条任务记录，前端可通过 API 查询「跑完了没有、结果是什么」。

## 为什么需要？

Phase 4 只有 `run_deep_agent()`：

- CLI 跑完就结束，没有「查询历史任务」的能力
- HTTP 接口必须**立即返回** `thread_id`，Agent 在后台跑——前端需要轮询或 WebSocket 拿结果
- 没有 store，就无法回答「这个任务现在什么状态」

## 状态流转

```
pending  →  running  →  done
                    ↘  error
```

| 状态 | 含义 | 谁写入 |
|------|------|--------|
| `pending` | 已创建，尚未执行 | `server.py` 的 `task_store.create` |
| `running` | Agent 正在跑 | `runner.py` 的 `mark_running` |
| `done` | 成功完成 | `runner.py` 的 `mark_done` |
| `error` | 异常退出 | `runner.py` 的 `mark_error` |

## 一条任务记录长什么样？

```json
{
  "thread_id": "abc-123",
  "query": "查 Sprint-12 开放缺陷",
  "status": "done",
  "result": "## 总结\n...",
  "error": null,
  "session_dir": "F:/.../output/session_abc-123",
  "created_at": "2026-06-04T10:00:00+00:00",
  "updated_at": "2026-06-04T10:02:30+00:00"
}
```

## 关键代码

```python
class TaskStore:
    def __init__(self):
        self._lock = threading.Lock()  # 多协程/多请求并发安全
        self._tasks: Dict[str, Dict] = {}

task_store = TaskStore()  # 全局单例
```

- **`threading.Lock`**：FastAPI 可能同时处理多个请求，防止字典读写冲突
- **内存存储**：MVP 够用；进程重启后丢失（V2 可换 Redis）

## 在项目中的位置

```
api/server.py
  create() ──────────────────→  POST /api/tasks 返回后立即记录
  get()    ←──────────────────  GET /api/tasks/{id}

agent/mainagent/runner.py
  mark_running / mark_done / mark_error / set_session_dir
```

CLI 试跑时，`runner` 发现没有记录会自动 `create`，所以不经过 API 也能用。

## 如何验证

```bash
# 提交任务后记住 thread_id
curl http://localhost:8000/api/tasks/{thread_id} -H "X-API-Key: dev-api-key"
```

多次查询应看到 `status` 从 `pending` → `running` → `done`。

## 学习要点

- 这是典型的 **异步任务 + 状态轮询** 模式（和 Celery job id 类似，只是 MVP 用内存）
- `thread_id` = 业务会话 ID = LangGraph checkpoint 的 `thread_id` = WebSocket 路由参数——**同一个 ID 贯穿全链路**
