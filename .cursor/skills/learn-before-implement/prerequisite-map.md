# Phase 前置知识地图

学习某 Phase 前，Agent 用本表诊断。缺项必须先补，再读项目代码。

## Phase 1：单 Agent + 单工具

| 前置 | 说明 | 官方/学习资源 |
|------|------|---------------|
| Python 函数与类型 | 能读 def、类型注解 | Python 教程函数章 |
| LangChain messages | user / assistant / tool 消息 | LangChain messages 文档 |
| .env 与环境变量 | 配置不硬编码 | pydantic-settings 文档 |

**项目落点**：`tools/upload_file_read_tool.py`、`agent/test_run.py`

---

## Phase 2：LLM 连接

| 前置 | 说明 |
|------|------|
| HTTP 基础 | URL、Header、API Key |
| OpenAI 兼容 API | chat/completions 概念 |
| httpx / requests | 同步与异步 HTTP 客户端 |

**项目落点**：`llm/model.py`、`config/settings.py`

---

## Phase 3：基建（config / context / prompt）

| 前置 | 说明 |
|------|------|
| ContextVar | 协程级变量，防串台 |
| YAML | prompts.yml 结构 |
| pathlib | 路径处理 |

**项目落点**：`context/session.py`、`prompt/loader.py`

---

## Phase 4：工具层 + 子 Agent

| 前置 | 说明 |
|------|------|
| MySQL SELECT | 只读查询 |
| DeepAgents subagents | task 工具委派 |
| LangGraph astream | chunk 里 model/tools 节点 |

**项目落点**：`tools/db_tools.py`、`agent/subagent/`、`agent/mainagent/runner.py`

---

## Phase 5：API + WebSocket + 任务状态（当前痛点）

| 前置 | 必须掌握到什么程度 |
|------|-------------------|
| 同步 vs 异步 | 知道阻塞会卡住事件循环 |
| async / await | 能读 `async def` 和 `await` |
| asyncio 事件循环 | 知道「一条 loop 调度很多协程」 |
| asyncio.create_task | 知道「先返回 HTTP，后台继续跑」 |
| HTTP vs WebSocket | 知道轮询 vs 服务端 push |
| FastAPI 路由 | 能读 `@app.post`、`@app.websocket` |
| 字典存连接 | 理解 thread_id → socket 映射 |

**缺任意 2 项以上 → 禁止读完整 monitor.py/server.py，先走 phase5-async-websocket.md**

**项目落点**：`api/server.py`、`api/task_store.py`、`api/monitor.py`

---

## Phase 6：可观测性与硬化（规划中）

| 前置 | 说明 |
|------|------|
| 结构化日志 | JSON log、trace_id |
| pytest | 自动化测试 |
| API 鉴权 | Header、401 |

**项目落点**：`observability/logging.py`、未来 `tests/`

---

## 诊断输出模板

```markdown
## 学习诊断
- **目标**：[用户要学的内容]
- **已有基础**：[✓ 项列表]
- **缺口**：[1～3 项]
- **本轮只学**：[一个知识点名称]
- **预计引用**：[official-references 中的链接]
```
