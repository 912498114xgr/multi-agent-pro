# 迭代 R2：步骤级状态与可展示 Trace

> **学习目标**：看完本文能讲清——Trace 记什么、为何 ContextVar、和 WS 进度有何分工、面试时打开哪份文件。  
> **关联需求**：[面试含金量优化需求文档.md](面试含金量优化需求文档.md) 中的 **R2**  
> **模块速查**：[modules/08-trace.md](../modules/08-trace.md)  
> **前置**：建议先读 [迭代-R1-失败隔离学习指南.md](迭代-R1-失败隔离学习指南.md)

---

## 1. 一句话：这次迭代要解决什么

R1 解决了「终态对不对」；R2 解决「**事后能不能把整条链路讲清楚**」。

面试官问：

> 怎么知道挂在哪一步？耗时多少？是工具失败还是模型规划问题？

要能打开一份 **`trace.json` 或前端 Trace 面板**，按时间顺序指：session → 委派助手 → 工具起止/耗时 → 模型回复 → 终态。

---

## 2. 改造前的痛点（为什么要动）

| 已有（R1 后） | 仍缺 |
|---------------|------|
| `failed_steps` + `failures_summary` | 没有**成功**步骤，看不到完整时间线 |
| WS：`assistant_call` / 终态 | 只有进度播报，任务结束后无法「打开一份 Trace」 |
| session 目录有报告文件 | 没有结构化 `trace.json` |
| 工具软失败在子 Agent 内 | 主图 astream **看不到**内部工具 chunk |

若只靠 WS：刷新/断线后细节丢失，且故意不推每个 `tool_exec`（避免刷屏）→ **必须另有全量记录通道**。

---

## 3. 设计决策（为什么这么做）

### 3.1 Trace 与 Monitor 分工

| 通道 | 定位 | 内容 |
|------|------|------|
| **Monitor / WS** | 实时、精简 | 委派、失败汇总、终态（给用户看进度） |
| **Trace** | 事后、完整 | 每个工具成败 + `duration_ms` + assistant/model/status（给面试/排障） |

**为什么不把每个工具执行再推回 WS？**  
与日志降噪冲突；前端步骤区会再次爆炸。Trace 落盘 / API 拉一次即可。

### 3.2 仍用 ContextVar（同 R1 理由）

子 Agent 内工具：`hooks.report_tool` → `trace_tool_start`，`format_*` → `trace_tool_end`。  
不依赖改造 DeepAgents 内部以拿到子图 chunk（成本高）。

### 3.3 start / end 成对记耗时

- **start**：工具入口（hooks）记下 `perf_counter`  
- **end**：返回时算 `duration_ms`  
同名工具可重试多次（`list_sql_tables#2`），避免重入串时钟。

### 3.4 WS 仍做「最近 N 条补发」

Ring buffer（50 条）在重连时 `replay: true` 推历史进度——补的是**进度体验**，不是完整 Trace 替代品。

---

## 4. 代码做了哪些改造

### 4.1 新增文件

| 文件 | 作用 |
|------|------|
| [`context/trace.py`](../../context/trace.py) | `init_trace` / `trace_tool_start|end` / `trace_event` / `build_trace_document` |
| [`observability/trace_io.py`](../../observability/trace_io.py) | `write_trace` / `read_trace` → `session/trace.json` |
| [`docs/modules/08-trace.md`](../modules/08-trace.md) | 模块用途速查 |
| [`tests/test_trace.py`](../../tests/test_trace.py)、`test_trace_io.py` | 起止耗时、落盘、store 字段 |

### 4.2 改造文件

| 文件 | 改了什么 |
|------|----------|
| [`tools/hooks.py`](../../tools/hooks.py) | `report_tool` → `trace_tool_start`（默认仍不 print） |
| [`tools/tool_result.py`](../../tools/tool_result.py) | `format_ok/error` → `trace_tool_end`；失败仍 `record_failure` |
| [`agent/mainagent/runner.py`](../../agent/mainagent/runner.py) | `init_trace`；`assistant`/`model_result`/`session`/`status` 事件；`_persist_trace` 落盘 |
| [`api/task_store.py`](../../api/task_store.py) | 字段 `steps`、`trace_path`；`set_trace` / `mark_*` 可带 steps |
| [`api/server.py`](../../api/server.py) | `GET /api/tasks/{id}/trace` |
| [`api/monitor.py`](../../api/monitor.py) | 事件 ring buffer + connect 补发 |
| 前端 `client.js` / `App.vue` | `getTaskTrace`；右侧「链路 Trace」按钮 + 侧拉栏时间线 |

### 4.3 Trace 文档长什么样

**顶层：**

```json
{
  "thread_id": "...",
  "query": "...",
  "status": "error|partial_success|done",
  "started_at": "...",
  "finished_at": "...",
  "duration_ms": 12345,
  "session_dir": "...",
  "steps": [ ... ],
  "failed_steps": [ ... ]
}
```

**单条 step（工具）：**

```json
{
  "seq": 3,
  "kind": "tool",
  "name": "list_sql_tables",
  "role": "critical",
  "status": "error",
  "error_type": "upstream",
  "message": "Can't connect...",
  "duration_ms": 4094,
  "ts": "..."
}
```

**kind 取值：** `session` | `assistant` | `tool` | `model_result` | `status`

---

## 5. 数据流（建议背这张图）

```text
run_deep_agent
  init_trace + init_failure_steps
  trace_event(session)
       │
       ▼
  astream：委派子 Agent → trace_event(assistant) + WS assistant_call
       │
       ▼
  子 Agent 调工具
       hooks.report_tool → trace_tool_start
       format_tool_*    → trace_tool_end (+ failure_steps 若失败)
       │
       ▼
  主模型最终 content → trace_event(model_result) + WS task_result
       │
       ▼
  decide_task_status（R1）
  _persist_trace：status 事件 → write_trace → task_store.steps/trace_path
       │
       ▼
  前端 finalize → GET .../trace → 右侧「链路 Trace」侧拉栏
  磁盘：output/session_{id}/trace.json
```

---

## 6. 怎么本地验证（快速学习）

```powershell
python -m unittest discover -s tests -v

# 跑完一题后：
# 1) 点右侧「链路 Trace」打开侧拉栏
# 2) 打开 output/session_<thread_id>/trace.json
# 3) curl（需 API Key）：
#    GET http://localhost:8000/api/tasks/{id}/trace
```

对照检查：

- 断库：critical 工具多条 `status=error`，且有合理 `duration_ms`（连超时约数秒）  
- 仅搜索挂：search `error`，若写作成功应有 `generate_markdown` 的 `ok`  
- `failed_steps` 应与 Trace 里失败的 tool 步骤一致  

---

## 7. 面试怎么讲（30 秒版）

> 进度用 WebSocket 做精简实时播报；完整可解释性靠步骤级 Trace：工具 hooks 记 start、结构化返回记 end 与耗时，子 Agent 嵌套也走 ContextVar。任务结束落盘 `trace.json`，前端和 API 都能打开，用来定位是工具失败还是规划问题。

演示动作：打开 Trace 表，指一条 `assistant` + 后面几条 `tool`。

---

## 8. 推荐阅读顺序

1. 本文第 2～3 节  
2. [`docs/modules/08-trace.md`](../modules/08-trace.md)（文件表）  
3. [`context/trace.py`](../../context/trace.py) 文件头注释（最全）  
4. `hooks.report_tool` ↔ `format_tool_*` 的 start/end 配对  
5. `runner._persist_trace`  
6. 前端 `loadTraceForTask` + 侧拉栏  


---

## 9. R1 / R2 对照（一张表记住）

| 维度 | R1 失败隔离 | R2 Trace |
|------|-------------|----------|
| 核心问题 | 终态对不对 | 链路能不能讲清楚 |
| 关键结构 | `failed_steps`、`partial_success` | `steps`、`trace.json`、`trace_path` |
| 决策 | `decide_task_status` | 不决策，只记录 |
| 展示 | 状态标签 + 错误/降级文案 | 右侧侧拉栏时间线 / 打开 JSON |
| 依赖 | ContextVar 失败收集 | ContextVar Trace + hooks 起止 |

两轮合在一起，才形成可面试的故事：**既能隔离失败，又能展示证据。**
