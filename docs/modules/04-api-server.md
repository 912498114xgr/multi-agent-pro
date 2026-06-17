# 04 — `api/server.py`：FastAPI 服务入口

## 这是什么？

把 EfficiencyAgent 暴露为 **HTTP + WebSocket 服务** 的入口文件。前端 / Postman / curl 通过它提交任务，而不是只能跑 `test_run.py`。

## 为什么需要？

| 只有 CLI | 有 server |
|----------|-----------|
| 开发者本机手动跑 | 前端页面、其他服务可调用 |
| 无上传接口规范 | `POST /api/upload` 统一收文件 |
| 无鉴权 | `X-API-Key` 校验 |
| 无文件列表/下载 | `/api/files`、`/api/download` |

## 核心接口

| 方法 | 路径 | 作用 |
|------|------|------|
| POST | `/api/tasks` | 提交任务（主入口） |
| POST | `/api/task` | 兼容 deep_search_pro 的路径 |
| GET | `/api/tasks/{thread_id}` | 查询任务状态与结果 |
| POST | `/api/upload` | 上传文件到 `updated/session_{id}/` |
| GET | `/api/files` | 列出 output 目录下文件 |
| GET | `/api/download` | 下载生成的报告 |
| WS | `/ws/{thread_id}` | 实时接收 monitor 事件 |
| GET | `/health` | 健康检查（无需 API Key） |

## 最关键的设计：异步后台执行

```python
async def _start_task(request: TaskRequest) -> TaskResponse:
    thread_id = request.thread_id or str(uuid.uuid4())
    task_store.create(thread_id, request.query)
    asyncio.create_task(_run_task_background(request.query, thread_id))
    return TaskResponse(status="started", thread_id=thread_id)
```

**为什么不能等 Agent 跑完再返回？**

- Agent 可能跑 1～10 分钟
- HTTP 连接会超时
- 正确做法：**立刻返回 thread_id**，客户端用 WebSocket 或轮询拿进度

## 启动时绑定 WebSocket

```python
@app.on_event("startup")
async def startup_event():
    manager.set_loop(asyncio.get_running_loop())
```

把 FastAPI 的事件循环交给 `ConnectionManager`，这样 `runner` 里 `monitor._emit` 才能往 WebSocket 推消息。

## 鉴权

```python
def verify_api_key(x_api_key: Header(...)):
    if x_api_key != settings.api_key:
        raise HTTPException(401, ...)
```

请求头需带：`X-API-Key: dev-api-key`（与 `.env` 中 `API_KEY` 一致）。

## 在项目中的位置

```
用户/前端
    ↓ HTTP / WS
api/server.py
    ↓ create_task
api/task_store.py + agent/mainagent/runner.py
    ↓
tools / subagents / MySQL / LLM
```

## 如何启动

```bash
uvicorn api.server:app --reload --host 0.0.0.0 --port 8000
```

## 学习要点

- **CORS**：允许前端 `localhost:3000` 跨域访问
- **路径安全**：`/api/files` 和 `/api/download` 用 `is_relative_to(output_dir)` 防止目录遍历攻击
- 与 deep_search_pro 的 `server.py` 结构几乎一致，是本课程架构的「标准外壳」
