# 程序执行日志分析：大模型 Agent 如何工作

本文以一次**真实成功运行**的日志为线索，逐段对照源码，说明本项目中多 Agent 系统的完整执行链路。

**示例任务**：查询 `xiaoneng_db` 中 Sprint-12 迭代的开放缺陷并简要总结。

**入口命令**（IDEA Debug）：

```text
.venv\Scripts\python.exe agent\test_run.py
```

---

## 1. 整体架构



![1781664515225](F:\BaiduNetdiskDownload\alLearn\multi-agent-pro\docs\img\1781664515225.png)





**核心思想**：

| 角色 | 职责 |
|------|------|
| **主 Agent（效能负责人）** | 理解用户意图、规划步骤、委派子 Agent、汇总最终答案 |
| **子 Agent（数据查询助手）** | 在独立上下文中多次调用数据库工具，返回查数结果 |
| **LangGraph** | 以「图节点」方式驱动 `model → tools → model → ...` 循环 |
| **deepagents** | 在 LangGraph 上封装 `create_deep_agent`，提供 `task` 工具委派子 Agent |

---

## 2. 启动前：模块加载时发生了什么

在 `test_run.py` 执行 `main()` **之前**，Python 导入链已经组装好主 Agent。

### 2.1 加载 Prompt 与模型

```python
# agent/mainagent/runner.py（模块顶层，import 时执行）
_main_cfg = get_main_agent_prompt()      # 读 prompt/prompts.yml
model = get_model()                      # 读 config/settings.py + .env

main_agent = create_deep_agent(
    model=model,
    system_prompt=_main_cfg["system_prompt"],
    tools=[read_file_content],
    checkpointer=InMemorySaver(),
    subagents=ALL_SUBAGENTS,             # 5 个子 Agent
)
```

| 文件 | 作用 |
|------|------|
| `prompt/prompts.yml` | 主 Agent 与各子 Agent 的 `system_prompt`、`name`、`description` |
| `prompt/loader.py` | 校验 YAML 并返回配置 |
| `llm/model.py` | 初始化 `GLM-5`（或 `.env` 中配置的模型） |
| `agent/subagent/__init__.py` | 注册 5 个子 Agent，本次用到的是 `database_agent` |

主 Agent 的 system prompt 中写明了专家团队成员（摘自 `prompts.yml`）：

```yaml
你的专家团队成员：
  1. **数据查询助手** — 从 xiaoneng_db 查询需求、缺陷、迭代、工时等结构化数据
  2. **行业检索助手** — ...
  ...
```

因此当用户问「查 Sprint-12 开放缺陷」时，主 LLM 会优先委派 **数据查询助手**，而不是自己写 SQL。

---

## 3. 按时间线读执行日志

以下日志来自一次完整成功运行（`exit code 0`）。

---

### 阶段 0：程序入口

```text
Query: 请查询 xiaoneng_db 中 Sprint-12 迭代有哪些开放缺陷，并简要总结。
Session: cli-9444a046
```

**对应代码**：`agent/test_run.py`

```python
query = sys.argv[1] if len(sys.argv) > 1 else "请查询 xiaoneng_db 中 Sprint-12 ..."
session_id = f"cli-{uuid.uuid4().hex[:8]}"
await run_deep_agent(query, session_id)
```

| 变量 | 含义 |
|------|------|
| `query` | 用户自然语言任务 |
| `session_id` | 会话 ID，同时作为 LangGraph 的 `thread_id` 和工作目录后缀 |

---

### 阶段 1：会话准备

```text
task_query: 请查询 xiaoneng_db 中 Sprint-12 迭代有哪些开放缺陷，并简要总结。
session_id: cli-9444a046
session_dir: F:\...\output\session_cli-9444a046
session_dir_str: F:/.../output/session_cli-9444a046
relative_dir: output/session_cli-9444a046
upload_prompt: ''
uploaded_files: []
tokens: (Token(...), Token(...), Token(...), Token(...))
config: {'configurable': {'thread_id': 'cli-9444a046'}}
```

**对应代码**：`run_deep_agent()` 前半段 + `_prepare_session()`

```python
session_dir, session_dir_str, relative_dir, upload_prompt, uploaded_files = _prepare_session(session_id)
tokens = setup_request_context(session_dir_str, session_id)
config = {"configurable": {"thread_id": session_id}}
path_instruction = _build_path_instruction(relative_dir, upload_prompt)
user_content = task_query + path_instruction
```

**这一步在做什么**：

1. **建工作目录** `output/session_{id}/`，Agent 生成的报告会写到这里
2. **检查上传文件** `updated/session_{id}/`，有则复制到工作目录并追加 prompt
3. **设置 ContextVar**（`context/session.py`），让工具层能拿到当前会话目录和 thread_id
4. **拼 path_instruction**，告诉 LLM 文件读写规则（相对路径、禁止绝对路径等）

```text
[Monitor:session_created] 工作目录已创建: F:/.../output/session_cli-9444a046
```

**对应代码**：`monitor.report_session_dir(session_dir_str)` → `api/monitor.py` 的 `_emit("session_created", ...)`

---

### 阶段 2：注入用户消息，启动 Agent 图

```text
path_instruction:
    【工作环境指令】
    工作目录: output/session_cli-9444a046
    ...

input_messages: {'messages': [{'role': 'user', 'content': '请查询 xiaoneng_db...【工作环境指令】...'}]}
```

**对应代码**：

```python
async for chunk in main_agent.astream(input_messages, config=config):
```

送入图的状态只有一条 `HumanMessage`（用户消息 + 环境指令）。  
`config.thread_id` 让 `InMemorySaver` 能按会话隔离 checkpoint。

---

### 阶段 3：中间件预处理

```text
node_name: PatchToolCallsMiddleware.before_agent
state: {'messages': Overwrite(value=[HumanMessage(content="请查询 xiaoneng_db...")])}
```

| 字段 | 解读 |
|------|------|
| `node_name` | deepagents 内置中间件，在调模型前整理/修补 tool_calls |
| `HumanMessage` | LangChain 消息类型，表示用户输入 |
| `Overwrite(...)` | LangGraph 的状态更新方式，用新消息覆盖 messages |

**业务代码不直接写这个节点**，由 `create_deep_agent` 框架自动插入。看到它说明图已开始流转。

---

### 阶段 4：主 Agent 第一次调用 LLM —— 决定委派

```text
node_name: model
state: {'messages': [AIMessage(
  content='',
  tool_calls=[{
    'name': 'task',
    'args': {
      'description': '查询 xiaoneng_db 中 Sprint-12 迭代的开放缺陷。\n\n步骤：\n1. 先列出数据库中的表...',
      'subagent_type': '数据查询助手'
    }
  }],
  response_metadata={'finish_reason': 'tool_calls', 'model_name': 'GLM-5'}
)]}
```

**对应代码**：`runner.py` 中 `node_name == "model"` 分支

```python
if last_msg.tool_calls:
    for tool_call in last_msg.tool_calls:
        if name == "task":
            monitor.report_assistant(args.get("subagent_type", ""), ...)
```

**如何读这条 AIMessage**：

| 字段 | 值 | 含义 |
|------|-----|------|
| `content` | `''` | 这次模型不直接回答用户，而是选择行动 |
| `finish_reason` | `tool_calls` | 模型输出是工具调用，流程继续 |
| `name` | `task` | deepagents 的「委派子 Agent」工具 |
| `subagent_type` | `数据查询助手` | 匹配 `database_agent["name"]` |
| `description` | 多步查库说明 | 传给子 Agent 的任务描述 |

```text
[Monitor:assistant_call] 正在调用助手: 数据查询助手
tool_call_name: task
tool_call_args: {'description': '...', 'subagent_type': '数据查询助手'}
```

主 Agent **没有**直接连数据库，而是把查库任务交给子 Agent。这正是 `prompts.yml` 里「效能负责人协调专家」的设计。

**子 Agent 定义**（`agent/subagent/database_agent.py`）：

```python
database_agent = {
    "name": _cfg["name"],           # "数据查询助手"
    "description": _cfg["description"],
    "system_prompt": _cfg["system_prompt"],
    "tools": [list_sql_tables, get_table_data, execute_sql_query],
}
```

```text
node_name: TodoListMiddleware.after_model
state: None
```

框架中间件收尾，`state: None` 表示本步无新消息，可忽略。

---

### 阶段 5：子 Agent 执行数据库工具（ReAct 循环）

子 Agent 在 `tools` 节点内部运行，日志以 `[Tool]` 和 `[SQL Audit]` 形式打印。

#### 5.1 列表明细

```text
[Tool] list_sql_tables args={}
[SQL Audit] tool=list_sql_tables ms=190.8 size=108 status=ok query=SHOW TABLES
```

**对应代码**：`tools/db_tools.py`

```python
@tool
def list_sql_tables() -> str:
    hooks.report_tool("list_sql_tables")          # → [Tool] 日志
    ...
    cursor.execute("SHOW TABLES")
    _audit("list_sql_tables", "SHOW TABLES", ...)  # → [SQL Audit] 日志
```

子 Agent 按 `prompts.yml` 推荐流程：**先 list_sql_tables 了解库结构**。

#### 5.2 预览表结构

```text
[Tool] get_table_data args={'table_name': 'defects'}
[Tool] get_table_data args={'table_name': 'iterations'}
[SQL Audit] ... query=SELECT * FROM `defects` LIMIT 100
[SQL Audit] ... query=SELECT * FROM `iterations` LIMIT 100
```

**对应代码**：

```python
@tool
def get_table_data(table_name: str) -> str:
    hooks.report_tool("get_table_data", {"table_name": table_name})
    sql = f"SELECT * FROM `{table_name}` LIMIT 100"
```

子 Agent 从表数据推断字段含义（如 `iteration_code`、`status`）。

#### 5.3 执行精确 SQL

```text
[Tool] execute_sql_query args={'query': "
SELECT d.defect_id, d.defect_code, d.title, ...
FROM defects d
JOIN iterations i ON d.iteration_id = i.iteration_id
WHERE i.iteration_code = '2026-Sprint-12'
  AND d.status = 'open'
"}
[SQL Audit] tool=execute_sql_query ms=36.1 size=431 status=ok
```

子 Agent 又执行了：

- 带 `team_members` JOIN 的明细查询（补负责人姓名）
- `COUNT(*)` 统计总数
- `get_table_data(team_members)` 确认成员表结构

这是典型的 **ReAct（推理 + 行动）** 模式：

```text
观察（表列表）→ 行动（预览表）→ 观察（字段）→ 行动（写 SQL）→ 观察（结果）→ 行动（补全 JOIN）→ 完成
```

**安全机制**（`tools/sql_validator.py`）：

- `execute_sql_query` 仅允许只读 SQL（SELECT / SHOW / DESCRIBE）
- `get_table_data` 校验表名白名单
- 异常返回字符串而非抛错，避免打断 Agent 流程

---

### 阶段 6：工具结果返回主 Agent

```text
node_name: tools
state: {'messages': [ToolMessage(
  content='## Sprint-12 迭代开放缺陷查询结果\n\n### 开放缺陷明细（共 3 条）...',
  name='task',
  tool_call_id='call_78a82a0e4e7a4ed990f256e3'
)]}
tool_result_name: task
tool_result_content_preview: ## Sprint-12 迭代开放缺陷查询结果...
```

| 消息类型 | 含义 |
|----------|------|
| `ToolMessage` | 某次 `tool_calls` 的执行结果 |
| `name='task'` | 对应主 Agent 发起的 `task` 工具调用 |
| `tool_call_id` | 与 AIMessage 中的 `call_xxx` 一一对应 |

**对应代码**：`runner.py` 中 `node_name == "tools"` 分支打印预览。

子 Agent 返回的是**整理好的 Markdown 表格**（3 条开放缺陷、严重程度、负责人等），不是原始 CSV。子 Agent 的 system prompt 要求「返回完整查询结果，供后续分析使用」。

---

### 阶段 7：主 Agent 第二次调用 LLM —— 最终总结

```text
node_name: model
state: {'messages': [AIMessage(
  content='## Sprint-12 迭代开放缺陷总结\n\n**迭代概况**：...',
  tool_calls=[],
  response_metadata={'finish_reason': 'stop', 'model_name': 'GLM-5'}
)]}
```

| 字段 | 含义 |
|------|------|
| `content` 有值 | 给用户的最终自然语言回答 |
| `tool_calls=[]` | 不再调用工具 |
| `finish_reason: stop` | 模型认为任务完成 |

```text
主智能体执行结果，最终结果：## Sprint-12 迭代开放缺陷总结...
[Monitor:task_result] 任务执行完成
```

**对应代码**：

```python
elif last_msg.content:
    preview = content[:100]
    print(f"主智能体执行结果，最终结果：{preview}")
    monitor.report_task_result(content)
```

主 Agent 在子 Agent 原始数据基础上做了**业务向总结**：

- 强调 prod 环境缺陷需紧急处理
- 指出王浩负载集中
- 3 条缺陷均创建于同一天

这符合 `prompts.yml` 中「纯问答：只查数 → 汇总后直接回答」的任务类型。

---

### 阶段 8：收尾

```text
node_name: TodoListMiddleware.after_model
state: None
reset_all_tokens: (Token(...), ...)
Process finished with exit code 0
```

**对应代码**：

```python
finally:
    reset_all_tokens(tokens)   # 清理 ContextVar，防止污染下一个协程
```

---

## 4. Agent 循环模型（通用读日志法）

任意一次任务，LangGraph 大致按此循环运转：

```text
HumanMessage（用户输入）
    ↓
[before_agent 中间件]
    ↓
model（LLM 思考）
    ├─ finish_reason=tool_calls → tools（执行工具/子Agent）→ ToolMessage → 回到 model
    └─ finish_reason=stop       → 最终 AIMessage → 结束
    ↓
[after_model 中间件]
```

**本次任务的完整消息链**：

```text
HumanMessage(用户问题 + 环境指令)
  → AIMessage(tool_calls=[task → 数据查询助手])
  → [子Agent 内部多轮 Tool 调用]
  → ToolMessage(查库结果 Markdown)
  → AIMessage(最终总结, stop)
```

---

## 5. 日志前缀速查表

| 日志前缀 | 来源文件 | 说明 |
|----------|----------|------|
| `Query:` / `Session:` | `agent/test_run.py` | CLI 入口参数 |
| `task_query:` / `session_id:` / `config:` 等 | `agent/mainagent/runner.py` | 调试变量打印 |
| `[Monitor:session_created]` | `api/monitor.py` | 工作目录就绪 |
| `[Monitor:assistant_call]` | `api/monitor.py` | 主 Agent 委派子 Agent |
| `[Monitor:task_result]` | `api/monitor.py` | 任务完成 |
| `[Monitor:error]` | `api/monitor.py` | 异常（如 LLM Connection error） |
| `node_name:` / `state:` | `runner.py` astream 循环 | **Agent 图节点输出，调试核心** |
| `[Tool]` | `tools/hooks.py` | 某个 `@tool` 被调用 |
| `[SQL Audit]` | `tools/db_tools.py` | SQL 耗时、大小、状态 |
| `主智能体执行结果...` | `runner.py` | 最终回答前 100 字预览 |

---

## 6. 关键源码文件地图

```text
agent/test_run.py              # CLI 入口，生成 session_id，调用 run_deep_agent
agent/mainagent/runner.py      # 主 Agent 组装 + astream 循环 + 进度上报
agent/subagent/database_agent.py  # 数据查询子 Agent 配置
prompt/prompts.yml             # 主/子 Agent 的 system_prompt（决定行为）
prompt/loader.py               # 加载并校验 prompts.yml
llm/model.py                   # GLM-5 / OpenAI 兼容 API 客户端
tools/db_tools.py              # list_sql_tables / get_table_data / execute_sql_query
tools/hooks.py                 # [Tool] 日志钩子
tools/sql_validator.py         # SQL 只读校验
context/session.py             # 协程级 session_dir / thread_id
api/monitor.py                 # [Monitor:*] 进度事件
config/settings.py             # .env 配置（模型、MySQL 等）
```

---

## 7. 本次业务结果摘要

| 项目 | 值 |
|------|-----|
| 迭代编码 | `2026-Sprint-12`（名称 Agent，进行中） |
| 开放缺陷数 | 3 条 |
| Critical | BUG-2026-0122（session，test） |
| Major（prod） | BUG-2026-0123（trace_id，需优先） |
| Minor | BUG-2026-0121 |

---

## 8. 常见问题：从日志快速定位

| 现象 | 可能原因 | 查哪里 |
|------|----------|--------|
| 卡在第一个 `node_name: model` 后报错 | LLM API 连不上 | `.env` 的 `OPENAI_*`；`llm/model.py` 代理设置 |
| 有 `[Monitor:assistant_call]` 但无 `[Tool]` | 子 Agent 内部 LLM 失败 | 同上 |
| 有 `[Tool]` 但 `[SQL Audit] status=fail` | MySQL 配置或 SQL 校验失败 | `.env` 的 `MYSQL_*`；`sql_validator.py` |
| `finish_reason=tool_calls` 一直循环 | 模型认为任务未完成 | `prompts.yml` 是否引导过早结束 |
| `subagent_type` 选错助手 | 主 Agent 规划问题 | `prompts.yml` 的 `main_agent.system_prompt` |

---

## 9. 小结

本项目的 Agent 工作方式可以概括为：

1. **Prompt 驱动规划**：`prompts.yml` 定义主 Agent「效能负责人」和 5 个专家子 Agent 的能力边界。
2. **图驱动执行**：`create_deep_agent` + LangGraph 以 `model ↔ tools` 循环推进任务。
3. **委派而非直连**：主 Agent 通过 `task` 工具把查库交给「数据查询助手」，子 Agent 再 ReAct 式调用 `db_tools`。
4. **可观测**：`runner.py` 打印图节点状态；`hooks` / `db_tools` / `monitor` 分层打点。
5. **会话隔离**：`session_id` 同时用于工作目录、`thread_id` checkpoint、ContextVar 上下文。

读懂日志的关键：**先看 `node_name` 判断在哪个图节点，再看 `messages` 最后一条的消息类型（Human / AI / Tool）和 `finish_reason`。**

---

## 10. astream 逐步 Chunk 日志（结构化）

本节把 `main_agent.astream()` **每一次 yield 的 chunk** 拆成固定字段，按真实运行日志逐条列出。

### 10.0 阅读说明

**一个 chunk 长什么样？** `runner.py` 里每次循环拿到的是：

```python
async for chunk in main_agent.astream(input_messages, config=config):
    # chunk 示例：{"model": {"messages": [AIMessage(...)]}}
    for node_name, state in chunk.items():
        ...
```

| 字段 | 含义 |
|------|------|
| `chunk_id` | 本文档编号，从 `#000` 输入开始，`#001` 起为 astream 每次 yield |
| `node_name` | 当前执行的图节点名（chunk 的 dict key） |
| `state` | 该节点输出的状态增量；`None` 表示本步无消息更新 |
| `message` | 从 `state["messages"][-1]` 解析出的结构化消息（无 messages 则为 `null`） |
| `side_logs` | 本 chunk 执行期间控制台出现的其他日志（Monitor / Tool / SQL Audit） |
| `checkpoint_messages` | 执行完本 chunk 后，图内**累积**的消息序列（逻辑视图） |

> `astream` 每个 chunk 通常只带**本步新增**的那 1 条 message，不是全量历史。`checkpoint_messages` 是人工串起来的完整对话链。

---

### Chunk #000 — astream 输入（非 yield，调用前）

```yaml
chunk_id: "#000"
source: runner.py 构造 input_messages
node_name: null
state: null

input:
  thread_id: cli-9444a046
  messages:
    - role: user
      type: HumanMessage
      content: |
        请查询 xiaoneng_db 中 Sprint-12 迭代有哪些开放缺陷，并简要总结。
        【工作环境指令】
        工作目录: output/session_cli-9444a046
        规则：
        1. 新生成文件必须保存到工作目录：'output/session_cli-9444a046/filename'
        2. 读取已上传文件时，filename 只传文件名，不带目录前缀
        3. 使用相对路径，禁止使用绝对路径
        4. 若存在上传文件，请先分析内容

side_logs:
  - "[Monitor:session_created] 工作目录已创建: F:/.../output/session_cli-9444a046"

checkpoint_messages:
  - "#1 HumanMessage  用户任务 + 工作环境指令"
```

---

### Chunk #001 — 中间件：进入 Agent 图

```yaml
chunk_id: "#001"
node_name: PatchToolCallsMiddleware.before_agent

state:
  messages_update: Overwrite   # LangGraph 覆盖式写入
  messages_count: 1

message:
  type: HumanMessage
  id: 7391da66-883f-48c6-9da0-0b6d8f71a884
  role: user
  content: |
    请查询 xiaoneng_db 中 Sprint-12 迭代有哪些开放缺陷，并简要总结。
    【工作环境指令】
    工作目录: output/session_cli-9444a046
    ...
  tool_calls: null

runner_prints:
  node_name: PatchToolCallsMiddleware.before_agent
  last_msg_type: HumanMessage
  messages_count: 1

side_logs: []

checkpoint_messages:
  - "#1 HumanMessage  用户任务 + 工作环境指令"

解读: 框架中间件整理消息，准备调 LLM。业务代码未介入。
```

---

### Chunk #002 — 主 LLM 第 1 次推理：委派子 Agent

```yaml
chunk_id: "#002"
node_name: model

state:
  messages_count: 1

message:
  type: AIMessage
  id: lc_run--019ecfb4-ca93-7f90-af01-893a3e5516ac-0
  role: assistant
  content: ""                    # 空：不直接回答用户
  finish_reason: tool_calls      # 还要执行工具
  model_name: GLM-5
  token_usage:
    prompt_tokens: 6910
    completion_tokens: 200
    total_tokens: 7110
  tool_calls:
    - id: call_78a82a0e4e7a4ed990f256e3
      name: task
      type: tool_call
      args:
        subagent_type: 数据查询助手
        description: |
          查询 xiaoneng_db 中 Sprint-12 迭代的开放缺陷。
          步骤：
          1. 先列出数据库中的表，了解表结构
          2. 找到与缺陷（bug/defect）和迭代（sprint/iteration）相关的表
          3. 预览相关表的数据结构，了解字段含义
          4. 执行 SQL 查询 Sprint-12 迭代中状态为"开放"的缺陷
          5. 返回完整的查询结果，不要省略

runner_prints:
  node_name: model
  last_msg_type: AIMessage
  tool_calls: "[{name: task, subagent_type: 数据查询助手, ...}]"
  tool_call_name: task
  tool_call_args: "{subagent_type: 数据查询助手, description: ...}"

side_logs:
  - "[Monitor:assistant_call] 正在调用助手: 数据查询助手"

checkpoint_messages:
  - "#1 HumanMessage   用户任务 + 工作环境指令"
  - "#2 AIMessage      content=空, tool_calls=[task→数据查询助手]"

解读: 主 Agent 决定不自己查库，通过 task 工具委派「数据查询助手」。
```

---

### Chunk #003 — 中间件：model 节点后处理

```yaml
chunk_id: "#003"
node_name: TodoListMiddleware.after_model

state: null                      # 无 messages 更新

message: null

runner_prints:
  node_name: TodoListMiddleware.after_model
  state: None
  # runner.py 遇到 state=None 或没有 messages 会 continue，不解析 message

side_logs: []

checkpoint_messages:             # 与 #002 相同，无新增
  - "#1 HumanMessage"
  - "#2 AIMessage      tool_calls=[task→数据查询助手]"

解读: 框架收尾节点，可忽略。
```

---

### Chunk #004 — tools 节点：子 Agent 查库并返回

> 主图只 yield **1 个** chunk，但节点内部子 Agent 会多次调 DB 工具。`side_logs` 列出这期间的全部控制台输出。

```yaml
chunk_id: "#004"
node_name: tools

state:
  messages_count: 1
  files: {}                      # 本步未写文件

message:
  type: ToolMessage
  id: 908657ab-a33f-444f-a5ac-4b5a1135a323
  name: task                     # 对应 Chunk #002 的 tool_call
  tool_call_id: call_78a82a0e4e7a4ed990f256e3
  role: tool
  content: |
    ## Sprint-12 迭代开放缺陷查询结果

    ### 迭代信息
    | 迭代编码 | 2026-Sprint-12 |
    | 迭代名称 | Agent |
    | 起止日期 | 2026-06-02 ~ 2026-06-13 |
    | 迭代状态 | active（进行中） |

    ### 开放缺陷明细（共 3 条）
    | # | 缺陷编码 | 标题 | 严重程度 | 状态 | 环境 | 负责人 | 报告人 |
    | 1 | BUG-2026-0122 | session | critical | open | test | 王浩 | 刘婷 |
    | 2 | BUG-2026-0123 | trace_id | major | open | prod | 王浩 | 孙凯 |
    | 3 | BUG-2026-0121 | （无标题） | minor | open | test | 赵磊 | 孙凯 |

    ### 关键发现
    - 开放缺陷总数：3 条
    - prod 缺陷 1 条：BUG-2026-0123
    - critical 缺陷 1 条：BUG-2026-0122

runner_prints:
  node_name: tools
  last_msg_type: ToolMessage
  tool_result_name: task
  tool_result_content_preview: "## Sprint-12 迭代开放缺陷查询结果..."

side_logs:                       # 子 Agent 内部执行，同属本 chunk 期间
  - "[Tool] list_sql_tables args={}"
  - "[SQL Audit] tool=list_sql_tables ms=190.8 status=ok query=SHOW TABLES"
  - "[Tool] get_table_data args={'table_name': 'defects'}"
  - "[Tool] get_table_data args={'table_name': 'iterations'}"
  - "[SQL Audit] tool=get_table_data ms=31.9 query=SELECT * FROM `defects` LIMIT 100"
  - "[SQL Audit] tool=get_table_data ms=31.3 query=SELECT * FROM `iterations` LIMIT 100"
  - "[Tool] execute_sql_query args={query: SELECT ... iteration_code='2026-Sprint-12' AND status='open'}"
  - "[SQL Audit] tool=execute_sql_query ms=36.1 status=ok"
  - "[Tool] execute_sql_query args={query: SELECT ... LEFT JOIN team_members ...}"
  - "[Tool] execute_sql_query args={query: SELECT COUNT(*) ...}"
  - "[SQL Audit] tool=execute_sql_query ms=21.6 status=ok  (COUNT)"
  - "[SQL Audit] tool=execute_sql_query ms=83.1 status=ok  (JOIN team_members)"
  - "[Tool] get_table_data args={'table_name': 'team_members'}"
  - "[SQL Audit] tool=get_table_data ms=16.4 query=SELECT * FROM `team_members` LIMIT 100"

checkpoint_messages:
  - "#1 HumanMessage   用户任务 + 工作环境指令"
  - "#2 AIMessage      tool_calls=[task→数据查询助手]"
  - "#3 ToolMessage    name=task, 查库结果 Markdown（3 条缺陷）"

解读: task 工具启动子 Agent → 子 Agent ReAct 查库 → 汇总为 ToolMessage 回传主 Agent。
```

---

### Chunk #005 — 主 LLM 第 2 次推理：输出最终总结

```yaml
chunk_id: "#005"
node_name: model

state:
  messages_count: 1

message:
  type: AIMessage
  id: lc_run--019ecfb6-03cb-7c73-9aaf-ea24af289053-0
  role: assistant
  content: |
    ## Sprint-12 迭代开放缺陷总结

    **迭代概况**：Sprint-12（编码 2026-Sprint-12，名称 Agent），6月2日–6月13日，当前状态为进行中。

    ### 开放缺陷明细（共 3 条）
    | 缺陷编码 | 标题 | 严重程度 | 环境 | 负责人 | 报告人 |
    | BUG-2026-0122 | session | Critical | test | 王浩 | 刘婷 |
    | BUG-2026-0123 | trace_id | Major | prod | 王浩 | 孙凯 |
    | BUG-2026-0121 | （无标题） | Minor | test | 赵磊 | 孙凯 |

    ### 关键发现
    1. 线上(prod)缺陷需紧急处理：BUG-2026-0123
    2. Critical 缺陷 1 条：BUG-2026-0122
    3. 负责人负载集中：王浩承担 2 条
    4. 3 条缺陷均创建于 6 月 4 日
  finish_reason: stop            # 任务结束，不再调工具
  model_name: GLM-5
  token_usage:
    prompt_tokens: 7571
    completion_tokens: 372
    total_tokens: 7943
    cached_tokens: 6848
  tool_calls: []                 # 空：无后续工具调用

runner_prints:
  node_name: model
  last_msg_type: AIMessage
  主智能体执行结果: "## Sprint-12 迭代开放缺陷总结..."  # 仅打印前 100 字

side_logs:
  - "[Monitor:task_result] 任务执行完成"

checkpoint_messages:
  - "#1 HumanMessage   用户任务 + 工作环境指令"
  - "#2 AIMessage      tool_calls=[task→数据查询助手]"
  - "#3 ToolMessage    查库结果"
  - "#4 AIMessage      content=最终总结, finish_reason=stop"

解读: 主 Agent 读取 ToolMessage，生成面向用户的业务总结，stream 核心逻辑结束。
```

---

### Chunk #006 — 中间件：收尾

```yaml
chunk_id: "#006"
node_name: TodoListMiddleware.after_model

state: null
message: null

runner_prints:
  node_name: TodoListMiddleware.after_model
  state: None

side_logs:
  - "reset_all_tokens: (Token(...), Token(...), Token(...), Token(...))"
  - "Process finished with exit code 0"

checkpoint_messages:             # 与 #005 相同
  - "#1 HumanMessage"
  - "#2 AIMessage      tool_calls"
  - "#3 ToolMessage"
  - "#4 AIMessage      最终总结"

解读: 框架收尾 + runner finally 清理 ContextVar，进程正常退出。
```

---

### 10.1 全量 Chunk 一览表

| chunk_id | node_name | message.type | message.content | finish_reason | 是否关键 |
|:--------:|-----------|--------------|-----------------|---------------|:--------:|
| #000 | — | HumanMessage | 用户问题 + 环境指令 | — | 输入 |
| #001 | PatchToolCallsMiddleware.before_agent | HumanMessage | 同上 | — | 可忽略 |
| #002 | **model** | AIMessage | `""`（空） | tool_calls | **是** |
| #003 | TodoListMiddleware.after_model | — | — | — | 可忽略 |
| #004 | **tools** | ToolMessage | 查库结果 Markdown | — | **是** |
| #005 | **model** | AIMessage | 最终总结 | stop | **是** |
| #006 | TodoListMiddleware.after_model | — | — | — | 可忽略 |

**只需盯住 3 个关键 chunk：`#002` → `#004` → `#005`**

---

### 10.2 checkpoint_messages 变化轨迹

```text
#000 输入后:     [Human]

#001 后:         [Human]

#002 后:         [Human] → [AI: 委派 task]

#003 后:         [Human] → [AI: 委派 task]          （无变化）

#004 后:         [Human] → [AI: 委派] → [Tool: 查库结果]

#005 后:         [Human] → [AI: 委派] → [Tool: 查库] → [AI: 最终总结]   ← 完成

#006 后:         同上
```

---

### 10.3 对照 runner.py：哪些 chunk 会打印 message

```python
if not state or "messages" not in state:
    continue   # #003、#006 走这里，只有 node_name，无 last_msg

# 有 messages 的 chunk（#001 #002 #004 #005）会打印：
print(f"last_msg_type: {type(last_msg).__name__}")
print(f"last_msg: {last_msg}")
```

| chunk_id | 能否看到 last_msg | 原因 |
|:--------:|:-----------------:|------|
| #001 | 能 | 有 HumanMessage |
| #002 | 能 | 有 AIMessage + tool_calls |
| #003 | 不能 | state=None |
| #004 | 能 | 有 ToolMessage |
| #005 | 能 | 有 AIMessage + content |
| #006 | 不能 | state=None |

---

## 11. Chunk 原理解释：为什么是这样写的、大模型为什么那样回复

> 本节解答第十节里「chunk 为什么长那样」「大模型为什么 content 为空却带 tool_calls」等问题。建议先看完第十节的逐步日志，再来读这一节。

### 11.1 先分清两种「流」

很多人把 `astream` 理解成「大模型一个字一个字往外吐」，在本项目中**不是**。

| 类型 | 是什么 | 本项目 |
|------|--------|--------|
| **Token 流** | LLM 逐 token 输出 `"你"` `"好"` `"，"` … | 未使用 |
| **图节点流（Graph Stream）** | 每跑完**一个图节点**，yield 一次 | **就是这个** |

对应代码（`agent/mainagent/runner.py`）：

```python
async for chunk in main_agent.astream(input_messages, config=config):
    for node_name, state in chunk.items():
        ...
```

这里的 `chunk` **不是**大模型的一个字，而是：

> **LangGraph 里某个节点刚执行完，吐出来的「这一步的状态增量」。**

```text
节点 A 干完 → yield chunk #1
节点 B 干完 → yield chunk #2
节点 C 干完 → yield chunk #3
```

chunk 的数量 = 图里跑过的节点数（中间件也算节点），**不是** token 数。

---

### 11.2 chunk 为什么是 `{ node_name: state }`？

#### LangGraph 是「状态图」

`create_deep_agent` 搭了一张图，简化流程：

```text
before_agent 中间件
    ↓
model（调大模型）
    ↓
after_model 中间件
    ↓
tools（执行工具）
    ↓
（可能再回到 model，循环）
```

图里有一个共享状态 `state`，最重要字段是 `messages`（对话历史）。

每个节点：读 state → 做事 → 往 state 追加一点 → 交给下一节点。

#### 为什么 dict 的 key 是 node_name？

`astream` 要告诉你：**刚刚是谁跑完了**。

| 日志里的 chunk | 白话 |
|----------------|------|
| `before_agent: {...}` | 预处理中间件刚跑完，消息整理好了 |
| `model: {...}` | 调 LLM 的节点刚跑完，模型回复出来了 |
| `after_model: None` | model 后中间件跑完，但没改 messages |
| `tools: {...}` | 工具节点刚跑完，工具结果回来了 |

**key = 谁干的，value = 这一步产出了什么状态变化。**

#### 为什么 state 里经常只有 1 条 message？

`astream` 默认给的是**这一步的增量（delta）**，不是全量历史。

```text
checkpoint 内部（全量，内部维护）:
  [HumanMessage, AIMessage, ToolMessage, AIMessage]

chunk #002 打印给你的（增量）:
  [AIMessage]   ← 只有本步新增的那一条
```

全量历史存在 `InMemorySaver` + `thread_id` 里：

```python
config = {"configurable": {"thread_id": session_id}}
```

所以 `runner.py` 取 `messages[-1]` 合理——**本 chunk 新增的最后一条就是本步结果**。第十节里的 `checkpoint_messages` 是人工串起来的全量视图。

---

### 11.3 大模型为什么那样回复？（按 message 类型）

大模型遵守 **OpenAI 工具调用协议**（本项目经 `langchain-openai` 调 `GLM-5`）。

#### HumanMessage — 输入，不是模型生成的

```text
请查询 xiaoneng_db 中 Sprint-12...
【工作环境指令】工作目录: output/session_...
```

`runner.py` 把用户问题与环境规则拼在一起：

```python
user_content = task_query + path_instruction
input_messages = {"messages": [{"role": "user", "content": user_content}]}
```

对应第十节 **Chunk #000 / #001**。

#### 第一次 AIMessage：content 空 + tool_calls（Chunk #002）

```text
AIMessage(
  content='',
  finish_reason='tool_calls',
  tool_calls=[{name: 'task', subagent_type: '数据查询助手', ...}]
)
```

**为什么 content 是空的？**

模型这次选择是：**不直接回答，而是调用工具**。

| 形态 | content | tool_calls | finish_reason |
|------|---------|------------|---------------|
| 直接回答 | 有文字 | `[]` | `stop` |
| 调用工具 | 通常为空 | 有内容 | `tool_calls` |

这是协议设计：**行动（调工具）和说话（文本）分开**。

**为什么选 `task` 而不是自己写 SQL？**

`prompt/prompts.yml` 里主 Agent 被告知：

- 你是「效能负责人」，负责协调
- 查库有「数据查询助手」
- 用户问的是 xiaoneng_db 结构化数据

模型判断：查库任务 → 委派 `数据查询助手`。  
`description` 是写给子 Agent 的任务说明书。

#### 中间件 chunk：state 为 None（Chunk #003 / #006）

```text
node_name: TodoListMiddleware.after_model
state: None
```

该节点可能维护 todo 等，但**没有往 messages 追加消息**。  
`runner.py` 会 `continue`，所以没有 `last_msg`——**正常，可忽略**。

#### ToolMessage — 工具执行结果（Chunk #004）

```text
ToolMessage(
  name='task',
  tool_call_id='call_78a82a0e4e7a4ed990f256e3',
  content='## Sprint-12 迭代开放缺陷查询结果...'
)
```

协议要求成对出现：

```text
AIMessage:     我要调用 task，id=call_xxx     ← 请求
ToolMessage:   结果，tool_call_id=call_xxx     ← 响应
```

没有 ToolMessage，模型不知道查到了什么，无法写总结。

**为什么 `[Tool]` / `[SQL Audit]` 不单独成 chunk？**

它们发生在 **tools 节点内部**：

```text
tools 节点开始
  └─ 执行 task 工具
       └─ 启动「数据查询助手」子 Agent
            ├─ list_sql_tables      → [Tool]
            ├─ get_table_data       → [Tool]
            ├─ execute_sql_query    → [SQL Audit]
            └─ 子 Agent 汇总 Markdown
  └─ 封装成一条 ToolMessage
tools 节点结束 → yield Chunk #004
```

主图只关心 task **最终返回什么**；子 Agent 内部几次 SQL 不会各成一个 chunk。

#### 第二次 AIMessage：有 content + stop（Chunk #005）

```text
AIMessage(
  content='## Sprint-12 迭代开放缺陷总结...',
  tool_calls=[],
  finish_reason='stop'
)
```

此时模型看到的上下文（逻辑上）：

```text
1. HumanMessage   用户问题
2. AIMessage      我之前委派了数据查询助手
3. ToolMessage    查库结果（3 条缺陷）
4. （轮到我再次发言）
```

模型判断：数据齐了 → 输出总结 → 不再调工具 → `stop`。

主 Agent 层的 **ReAct**：

```text
Reason（推理）→ Act（task 委派）→ Observe（ToolMessage）→ Reason（总结）→ Stop
```

---

### 11.4 把 chunk 与模型回复串成一条故事

```text
【输入】你对图说：帮我查 Sprint-12 开放缺陷

【#001】before_agent — 图：消息整理好了（HumanMessage）

【#002】model — 大模型第 1 次想：这是查库任务，派数据查询助手
         输出 tool_calls=[task]，content 留空

【#003】after_model — 图：model 后处理完（无新消息）

【#004】tools — task 启动子 Agent，多次查 MySQL（[Tool] 日志），
         汇总 Markdown，yield 一条 ToolMessage

【#005】model — 大模型第 2 次想：有数据了，写业务总结
         content=总结，finish_reason=stop

【#006】after_model — 收尾，进程退出
```

**关键路径：`#002`（决定委派）→ `#004`（拿到数据）→ `#005`（输出答案）**

---

### 11.5 类比：项目经理 + 数据分析员

| 角色 | 对应 | 行为 |
|------|------|------|
| 你 | HumanMessage | 提需求 |
| 项目经理 | 主 Agent（model 节点） | 不亲自查表，派活 |
| 派工单 | AIMessage.tool_calls | `task(description=...)` |
| 数据分析员 | 子 Agent（tools 节点内） | 跑 SQL、整理报告 |
| 分析报告 | ToolMessage | 交给项目经理 |
| 给老板的摘要 | 第二次 AIMessage | 写 executive summary |

**chunk = 每完成一个环节，在日志本上记一行「谁刚干完了什么」**  
不是老板每说一个字记一行。

---

### 11.6 读日志的固定步骤（配合第十节）

```text
1. 看 node_name
   model          → 大模型刚想完
   tools          → 工具刚跑完
   *Middleware*   → 框架步骤，多半可忽略

2. 看 message.type
   HumanMessage   → 输入
   AIMessage      → 模型输出
   ToolMessage    → 工具/子 Agent 输出

3. 若是 AIMessage，看 finish_reason
   tool_calls     → 还要等 tools chunk
   stop           → 最终答案到了

4. 若是 AIMessage 且 tool_calls 非空
   name=task      → 委派子 Agent
   看 subagent_type → 派给了谁

5. 若是 ToolMessage
   看 tool_call_id 对应哪次调用
   content 就是子 Agent 的成果

6. [Tool] / [SQL Audit] 出现在两个 chunk 之间
   → 正在 Chunk #004 的 tools 节点内部，尚未 yield
```

---

### 11.7 常见困惑快答

| 问题 | 答案 |
|------|------|
| 为什么不是每个 SQL 一个 chunk？ | Chunk 是**图节点**粒度，不是工具粒度；所有 SQL 在同一 `tools` 节点内完成 |
| 为什么第一次 model 不直接回答？ | Prompt 要求委派专家 + 模型判断需要外部数据 |
| `state: None` 是不是错了？ | 不是，只是该节点没更新 `messages` |
| checkpoint 和 chunk 什么关系？ | 每 chunk 后增量合并进 checkpoint；下次 model 读**全量**，astream 只打印**增量** |
| chunk 和大模型 token 流的关系？ | 无关；本项目是节点级 stream，不是逐字输出 |

---

### 11.8 第十节 ↔ 第十一节 对照

| 第十节（是什么） | 第十一节（为什么） |
|------------------|-------------------|
| Chunk #002 AIMessage content 空 | 模型选择调工具，协议上 content 与 tool_calls 分工 |
| Chunk #004 只有一条 ToolMessage | tools 节点一次性返回；内部 SQL 是 side_logs |
| Chunk #003/#006 state=null | 中间件不更新 messages |
| checkpoint_messages 越来越长 | 增量 chunk + 内部 checkpoint 合并成全量 |
| 只需看 #002→#004→#005 | 主 Agent 的 Reason→Act→Observe→Reason→Stop |

