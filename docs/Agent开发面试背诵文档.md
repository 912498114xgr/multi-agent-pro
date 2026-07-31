# EfficiencyAgent Agent 开发面试背诵文档

适用岗位：后端开发 / AI Agent 开发 / LLM 应用工程师

项目路径：`F:\BaiduNetdiskDownload\alLearn\multi-agent-pro`

核心代码落点：

- `agent/mainagent/runner.py`
- `api/server.py`
- `api/monitor.py`
- `api/task_store.py`
- `context/session.py`
- `tools/sql_validator.py`

## 1. 项目介绍

### 1. 请用 1 分钟介绍这个项目。

**背诵答案：**

我做的是一个面向研发团队的 EfficiencyAgent，多 Agent 研发效能助手。用户用自然语言提出需求后，系统会自动查询 MySQL 里的需求、缺陷、迭代数据，读取上传材料，检索外部最佳实践，再由多个专家 Agent 协作完成指标分析，并生成周报、复盘或效能分析报告。后端用 FastAPI 提供任务提交、文件上传、状态查询和 WebSocket 进度推送。

**追问补充：**

强调它不是普通聊天，而是“查数 + 读文件 + 搜索 + 分析 + 生成报告”的闭环系统。

### 2. 这个项目解决什么业务痛点？

**背诵答案：**

研发 TL、PM 和效能工程师经常要手工查需求完成率、缺陷修复时效、迭代吞吐等数据，再结合测试报告和行业实践写周报或复盘。这个过程重复、耗时，而且容易漏掉关键数据。我的项目把这些步骤拆给不同 Agent 自动完成，让用户只需要描述目标，就能拿到结构化分析和报告。

**追问补充：**

可以举例：Sprint 复盘、周报、缺陷趋势分析、行业 benchmark 对比。

### 3. 为什么这个场景适合 Multi-Agent？

**背诵答案：**

因为这个任务天然包含多种能力：数据库查询、行业搜索、上传文件解读、指标分析、报告撰写。一个 Agent 拿所有工具容易职责混乱，也容易跳步骤。我把它拆成多个专家 Agent，由主 Agent 做规划和调度，每个子 Agent 只负责自己领域，工具权限更清晰，输出也更稳定。

**追问补充：**

拆分的核心收益是职责边界、工具权限、Prompt 聚焦和可扩展性。

### 4. 项目最重要的技术亮点是什么？

**背诵答案：**

我会重点讲三个：第一是主 Agent + 5 个子 Agent 的任务编排；第二是 FastAPI 长任务异步执行，用 `thread_id` 串起任务状态、WebSocket、checkpoint 和输出目录；第三是工程安全边界，包括 SQL 只读校验、ContextVar 会话隔离、文件路径限制和下载目录限制。

**追问补充：**

这三个点分别对应 Agent 架构、后端工程、企业落地安全。

### 5. 和参考项目有什么区别？

**背诵答案：**

我参考的是主 Agent 调度、FastAPI 和 WebSocket 的架构模式，但业务场景是原创的研发效能领域。参考项目偏行业搜索报告，我这个项目面向研发团队，增加了指标分析助手和报告撰写助手，并补了 SQL 只读、任务状态机、ContextVar 会话隔离和前后端实时进度闭环。

**追问补充：**

不要说“照搬”，要说“借鉴架构模式，业务和工程边界重新设计”。

## 2. Agent 架构

### 1. 为什么设计成主 Agent + 5 个子 Agent？

**背诵答案：**

主 Agent 负责理解用户意图和规划步骤，子 Agent 负责专业任务。我的 5 个子 Agent 分别是数据查询、行业检索、规范知识、指标分析和报告撰写。这样设计可以避免一个 Agent 同时拿数据库、搜索、文件生成等所有工具导致行为不可控，也能让每个 Agent 的 Prompt 更聚焦。

**追问补充：**

对应代码在 `agent/subagent/*.py` 和 `ALL_SUBAGENTS`。

### 2. 主 Agent 的职责是什么？

**背诵答案：**

主 Agent 是“效能负责人”。它不直接包办所有事情，而是判断用户任务类型，决定先查库、读文件、搜索实践，还是调用分析和写作助手。它直接绑定 `read_file_content`，因为上传材料常常是任务上下文的一部分；其他专业能力通过 DeepAgents 的子 Agent 委派完成。

**追问补充：**

主 Agent 组装在 `runner.py` 的 `create_deep_agent`。

### 3. 数据查询助手负责什么？

**背诵答案：**

数据查询助手绑定 `list_sql_tables`、`get_table_data`、`execute_sql_query`，负责只读访问 `xiaoneng_db`。它的目标是把需求、缺陷、迭代、工时等结构化数据查出来，以 CSV 风格返回给 LLM 阅读。SQL 执行前会经过只读校验，避免模型生成危险语句。

**追问补充：**

追问安全时转到 `tools/sql_validator.py`。

### 4. 行业检索助手负责什么？

**背诵答案：**

行业检索助手绑定 Tavily 搜索工具，负责补充外部研发效能实践，比如 DORA 指标、缺陷 SLA、敏捷复盘方法、行业 benchmark。它和数据库查询分开，是因为外部信息源的可靠性、检索方式和输出格式都不同。

**追问补充：**

外部实践用于建议和对标，不替代内部真实数据。

### 5. 规范知识助手为什么是 P1 / stub？

**背诵答案：**

规范知识助手规划上对接 RAGFlow，用于查询公司内部研发规范、发布流程和模板。MVP 阶段如果没有配置 RAGFlow，就返回未接入提示，而不是编造规范。这是一个工程取舍：先保留架构扩展点，后续再接真实知识库和权限控制。

**追问补充：**

面试时主动说“不编造内部规范”是加分点。

### 6. 指标分析助手为什么没有工具？

**背诵答案：**

指标分析助手只基于已经收集到的数据做趋势、异常、对比和建议分析，不再访问外部工具。这样可以降低分析阶段乱查数据或引入无关信息的风险，也能逼迫主 Agent 先完成事实收集，再进行分析。

**追问补充：**

这是“权限最小化”的 Agent 设计。

### 7. 报告撰写助手为什么单独拆出来？

**背诵答案：**

报告撰写助手绑定 `generate_markdown` 和 `convert_md_to_pdf`，负责把分析结果落盘成 Markdown 或 PDF。单独拆出来可以避免主 Agent 还没完成数据收集就写文件，也能集中控制文件生成路径，保证报告输出到当前 session 工作目录。

**追问补充：**

对应工具在 `tools/markdown_tools.py` 和 `tools/pdf_tools.py`。

## 3. 执行链路

### 1. 用户调用 `POST /api/tasks` 后发生什么？

**背诵答案：**

API 收到请求后先生成或接收 `thread_id`，调用 `task_store.create` 创建任务记录，然后用 `asyncio.create_task` 把 `run_deep_agent(query, thread_id)` 放到后台执行，HTTP 立即返回 `{status: "started", thread_id}`。之后前端通过 WebSocket 看进度，也可以通过 `GET /api/tasks/{thread_id}` 查询最终状态。

**追问补充：**

代码入口在 `api/server.py` 的 `_start_task`。

### 2. 为什么任务接口不直接返回结果？

**背诵答案：**

Agent 任务可能执行几十秒甚至几分钟，如果 HTTP 一直阻塞，容易遇到浏览器等待体验差、网关超时和无法展示中间进度的问题。所以我把“提交任务”和“执行任务”解耦，提交接口只返回任务 ID，后台协程执行，前端通过 WebSocket 和状态接口获取过程和结果。

**追问补充：**

这是典型长任务设计。

### 3. `thread_id` 有哪些作用？

**背诵答案：**

`thread_id` 是全链路会话标识。第一，它是 `task_store` 中任务状态的 key；第二，它是 WebSocket 定向推送的路由 key；第三，它是 LangGraph checkpoint 的 `configurable.thread_id`；第四，它还用于生成 `output/session_{thread_id}` 工作目录。

**追问补充：**

这题很高频，建议背熟。

### 4. `run_deep_agent` 的核心流程是什么？

**背诵答案：**

`run_deep_agent` 会先标记任务 running，再创建 `output/session_xxx`，复制上传文件，设置 ContextVar 上下文，然后构造工作目录指令并调用 `main_agent.astream`。执行过程中解析模型和工具 chunk，转成 monitor 事件推给 WebSocket。成功后 `mark_done`，异常时 `mark_error`，最后清理 ContextVar。

**追问补充：**

它是 CLI 和 API 共用的唯一执行入口。

### 5. `astream` 怎么转成进度？

**背诵答案：**

`main_agent.astream` 会流式返回 LangGraph 节点状态。runner 关注 `model` 节点最新 message：如果有 `tool_calls`，说明模型要调用工具或子 Agent；如果工具名是 `task`，就推送 `assistant_call`，否则推送 `tool_start`；如果有最终 content，就推送 `task_result` 并更新任务结果。

**追问补充：**

代码在 `_consume_agent_stream`。

### 6. 任务状态怎么流转？

**背诵答案：**

当前 MVP 里 `task_store` 是内存字典，状态从 `pending` 到 `running`，最后进入 `done` 或 `error`。创建任务时写入 query、thread_id、时间戳；Agent 开始执行时 mark_running；成功后写 result 和 session_dir；异常时写 error。

**追问补充：**

生产环境应换 Redis 或数据库。

## 4. 异步任务与 WebSocket

### 1. 为什么用 `asyncio.create_task`？

**背诵答案：**

因为 Agent 是耗时任务，不应该阻塞 HTTP 请求。`asyncio.create_task` 可以把协程登记到 FastAPI 当前事件循环里后台执行，让接口快速返回。这样前端拿到 `thread_id` 后，就可以连接 WebSocket 或轮询状态，用户体验更好，也避免 HTTP 长连接超时。

**追问补充：**

`_schedule_agent_task` 封装了这个逻辑。

### 2. WebSocket 如何推给正确任务？

**背诵答案：**

前端连接 `/ws/{thread_id}`，后端 `ConnectionManager` 保存 `thread_id -> WebSocket`。runner 执行时会通过 ContextVar 设置当前 `thread_id`，monitor 发事件时读取这个上下文，只把消息发给对应 thread 的连接。

**追问补充：**

这就是 `thread_id` 的路由作用。

### 3. `monitor.py` 为什么要保存 event loop？

**背诵答案：**

WebSocket 发送必须在 FastAPI 的事件循环里执行。monitor 可能在后台任务或其他上下文里被调用，所以启动时保存 FastAPI loop。发送时如果当前 loop 就是 manager loop，就 `create_task`；如果跨线程或没有 running loop，就用 `run_coroutine_threadsafe` 投递回 FastAPI loop。

**追问补充：**

这个点体现你理解 asyncio。

### 4. WebSocket 断了任务怎么办？

**背诵答案：**

当前设计中 WebSocket 断开只影响实时进度展示，不影响后台 Agent 执行。任务仍然会继续跑，最后状态和结果会写到 `task_store`，前端可以通过 `GET /api/tasks/{thread_id}` 查询。生产环境可以增加事件持久化和断线重连后的历史补发。

**追问补充：**

MVP 取舍要主动说清。

### 5. 当前 WebSocket 设计有什么限制？

**背诵答案：**

当前 `active_connections` 是 `Dict[str, WebSocket]`，也就是一个任务只保留一个连接，适合 MVP 的单页面演示。生产如果支持多标签页或多人协作，应改成 `Dict[str, Set[WebSocket]]`，并加心跳检测、断开清理、历史事件补发和鉴权。

**追问补充：**

这题适合谈生产化。

## 5. ContextVar 会话隔离

### 1. 为什么需要 `ContextVar`？

**背诵答案：**

FastAPI 是异步并发，同一个线程里可能同时跑多个请求。如果用全局变量保存当前 session 目录或 thread_id，很容易串台。`ContextVar` 提供协程级上下文，每个 Agent 任务都能有自己的 `session_dir`、`thread_id`、`trace_id` 和 `user_id`，工具层不用层层传参也能拿到当前会话信息。

**追问补充：**

对应 `context/session.py`。

### 2. 它解决了什么具体问题？

**背诵答案：**

比如两个用户同时生成报告，工具都要调用 `generate_markdown`。如果用全局变量保存输出目录，A 用户可能写到 B 用户目录。现在 runner 在任务开始时 `setup_request_context(session_dir, thread_id)`，工具通过 `get_session_context()` 获取当前协程的目录，所以文件读写被隔离在自己的 session 下。

**追问补充：**

结合文件工具回答更有说服力。

### 3. 为什么最后要 reset token？

**背诵答案：**

`ContextVar.set()` 会返回 token，代表设置前的上下文状态。runner 在 `finally` 中调用 `reset_all_tokens(tokens)`，可以保证任务结束或异常后都恢复上下文，避免污染后续协程。这是异步服务里非常重要的清理动作。

**追问补充：**

面试官会喜欢你提 `finally`。

### 4. `ContextVar` 和 `threading.local` 有什么区别？

**背诵答案：**

`threading.local` 是线程级隔离，但 asyncio 中多个协程可能跑在同一个线程里，所以它无法区分不同协程的上下文。`ContextVar` 是为异步任务设计的，可以随着协程上下文传播，更适合 FastAPI 这种 async 服务。

**追问补充：**

简短回答即可。

## 6. SQL 与文件安全

### 1. LLM 生成 SQL 有什么风险？

**背诵答案：**

模型可能生成 `DELETE`、`DROP`、多语句注入或超大查询。我的数据库工具把 SQL 执行限制为只读：只允许 `SELECT / SHOW / DESCRIBE / EXPLAIN`，禁止危险关键字，禁止分号多语句，并且返回结果最多截断到 100 行。

**追问补充：**

应用层校验不是唯一防线。

### 2. SQL 只读校验怎么做？

**背诵答案：**

`execute_sql_query` 在执行前调用 `validate_readonly_sql`。它先检查 SQL 非空，再去掉末尾分号，禁止中间出现分号，接着检查开头必须是只读语句，最后用黑名单正则拦截 `INSERT / UPDATE / DELETE / DROP / ALTER / CREATE` 等危险关键字。

**追问补充：**

代码在 `tools/sql_validator.py`。

### 3. 为什么还要生产只读账号？

**背诵答案：**

应用层校验可以防大部分 LLM 误生成危险 SQL，但它不应该是唯一防线。生产环境还应该给 Agent 使用数据库只读账号，从数据库权限层面禁止写操作。这样即使应用层有绕过，也不会造成真实数据破坏。

**追问补充：**

这是企业落地安全意识。

### 4. 文件读取怎么做安全限制？

**背诵答案：**

`read_file_content` 只支持 `.md .txt .docx .pdf .xlsx .xls`，不允许任意二进制或可执行文件。文件路径不是让模型传绝对路径，而是通过 ContextVar 获取当前 session 目录，再调用统一路径解析，限制在当前任务工作目录内读取。

**追问补充：**

代码在 `tools/upload_file_read_tool.py`。

### 5. 下载接口如何防目录遍历？

**背诵答案：**

`/api/download` 和 `/api/files` 会先把用户传入 path resolve 成绝对路径，再检查它是否位于 `output_dir.resolve()` 下。如果不在 output 目录内，就返回 403。这样即使用户传 `../` 也不能下载项目外文件。

**追问补充：**

对应 `api/server.py`。

### 6. 为什么上传文件要复制到 output session？

**背诵答案：**

上传文件先进入 `updated/session_{thread_id}`，Agent 执行时复制到 `output/session_{thread_id}`。这样本次任务的输入文件和生成报告在同一个工作目录，工具只需要面对一个 session 目录，便于上下文隔离、文件列表展示和后续下载。

**追问补充：**

逻辑在 `_prepare_session`。

## 7. 工程化取舍

### 1. 为什么配置集中在 `settings.py`？

**背诵答案：**

集中配置可以避免各模块到处 `os.getenv`，也方便类型校验、默认值管理和环境切换。我用 `pydantic-settings` 从项目根目录 `.env` 加载 API Key、CORS、LLM、MySQL、Tavily、RAGFlow、上传限制和路径配置。

**追问补充：**

`get_settings()` 用 `lru_cache` 做单例。

### 2. `llm/model.py` 有什么设计点？

**背诵答案：**

模型初始化显式读取 `OPENAI_BASE_URL`、`OPENAI_API_KEY`、`OPENAI_MODEL` 和超时时间，而不是依赖隐式环境变量。同时 httpx client 设置 `trust_env=False`，避免 Windows 开发环境继承系统代理导致连接中转接口失败。

**追问补充：**

这是本地开发稳定性经验。

### 3. `task_store` 为什么用内存？

**背诵答案：**

这是 MVP 取舍。内存 `task_store` 实现简单，足够展示 pending、running、done、error 的状态机和本地演示闭环。缺点是服务重启会丢任务，多实例部署无法共享状态。生产应该换 Redis 或数据库。

**追问补充：**

同理 checkpoint 也是 `InMemorySaver`。

### 4. 生产化你会优先改什么？

**背诵答案：**

我会优先做五件事：任务状态和 checkpoint 持久化到 Redis 或数据库；增加任务超时、取消和重试；WebSocket 支持多连接和断线补发；RAGFlow 真实接入并加权限控制；API Key 升级成用户鉴权和多租户隔离。

**追问补充：**

说“优先级”比泛泛罗列更好。

### 5. 如何评估 Agent 输出质量？

**背诵答案：**

我会从事实性、完整性、可执行性和格式稳定性评估。事实性看报告中的数字是否来自数据库或上传文件；完整性看是否覆盖用户要求的指标；可执行性看建议是否能落地；格式稳定性看 Markdown/PDF 是否符合模板。还可以沉淀典型任务作为回归用例。

**追问补充：**

可补充人工评审 + 自动检查。

## 8. 场景设计题

### 1. 用户要求生成 Sprint 复盘，Agent 顺序是什么？

**背诵答案：**

我会让主 Agent 先判断这是复盘类任务，然后调用数据查询助手查询 Sprint 的需求完成率、缺陷数、延期项等；如果用户上传了测试报告，就调用 `read_file_content` 读取；必要时调用行业检索助手补充实践；接着调用指标分析助手总结趋势和异常；最后委派报告撰写助手生成 Markdown。

**追问补充：**

顺序是收集事实、分析、写报告。

### 2. 用户上传 Excel 并要求结合数据库分析，怎么做？

**背诵答案：**

前端先把文件上传到 `updated/session_xxx`，任务启动后 runner 复制到 `output/session_xxx`。主 Agent 根据工作目录指令调用 `read_file_content` 读取 Excel 摘要，再调用数据查询助手查库，之后把两类数据交给指标分析助手，最后视用户要求生成报告。

**追问补充：**

Excel 工具返回行列、列名、前 5 行和统计。

### 3. 数据库没配置怎么办？

**背诵答案：**

数据库工具会检查 `settings.mysql_config()`，如果没有用户等必要配置，会返回“数据库未配置”的错误字符串，而不是直接抛异常打断 Agent。这样主 Agent 可以把数据缺口告知用户，或者继续基于上传文件和搜索结果完成部分分析。

**追问补充：**

工具异常返回字符串是 MVP 稳定性策略。

### 4. Tavily 搜索失败怎么办？

**背诵答案：**

搜索失败不应该让整个任务崩掉。主 Agent 应该说明外部 benchmark 暂时不可用，并基于数据库和上传文件完成核心分析。报告中要标注外部实践缺失，而不是编造行业数据。生产可以增加重试、降级搜索源和缓存。

**追问补充：**

强调“不编造”。

### 5. RAGFlow 未接入怎么办？

**背诵答案：**

规范知识助手在 MVP 阶段是规划能力，未配置 RAGFlow 时应返回未接入提示。主 Agent 可以告诉用户当前无法查询内部规范，只能基于已有数据和公开实践分析。后续 V2 再接真实 RAGFlow，并加入权限和知识库范围控制。

**追问补充：**

这是清晰的 MVP 边界。

### 6. 如果查询结果太大怎么办？

**背诵答案：**

当前数据库工具最多返回前 100 行，Excel 也只返回摘要、前几行和统计信息。这是为了防止把大表直接塞进 LLM 上下文。生产可以进一步做分页、聚合查询、采样、数据摘要和专门的指标计算工具。

**追问补充：**

体现上下文成本意识。

## 9. 高压追问

### 1. 你这是真 Multi-Agent，还是多个 Prompt？

**背诵答案：**

我认为它不是简单多个 Prompt 包装，因为每个子 Agent 都有明确职责和工具权限，主 Agent 通过 DeepAgents 的子任务机制进行委派。数据查询、搜索、规范、分析、写作在工具边界和输出目标上都不同，runner 还能把子 Agent 调用过程解析成实时事件。

**追问补充：**

关键是“职责 + 工具 + 调度 + 观测”。

### 2. 主 Agent 是强编排还是软调度？

**背诵答案：**

当前是软调度：主 Agent 根据 Prompt 规则决定调用哪些子 Agent，而不是后端写死 DAG。优点是灵活，能适配自然语言任务；缺点是稳定性依赖 Prompt 和模型。生产中可以对高频流程，比如周报和复盘，沉淀成半固定 workflow，提高稳定性。

**追问补充：**

这是成熟回答。

### 3. 如果模型跳步骤怎么办？

**背诵答案：**

我从两个层面约束：Prompt 中要求先收集数据，再分析，再写报告；工具层限制写文件只能通过报告撰写助手，并且文件路径受 session 控制。生产还可以增加 workflow guard，例如写报告前检查是否已有数据查询或分析结果。

**追问补充：**

当前是 Prompt 约束，后续加程序约束。

### 4. 如果两个 Agent 结论冲突怎么办？

**背诵答案：**

主 Agent 应该以数据来源优先级处理冲突：数据库和上传文件属于内部事实，优先级高；公网搜索只作为参考；规范知识取决于 RAGFlow 返回内容。报告中应明确数据来源和不一致点，而不是强行合并。生产可以加 citation 和证据链。

**追问补充：**

这个回答体现事实优先。

### 5. 多实例部署会有什么问题？

**背诵答案：**

当前内存 `task_store`、InMemory checkpoint 和内存 WebSocket 连接都只在单进程有效。多实例后，请求可能打到不同机器，任务状态和连接无法共享。生产需要 Redis/数据库存任务状态，持久 checkpoint，并通过消息队列或 sticky session 处理 WebSocket。

**追问补充：**

这是架构深挖重点。

## 10. 实战编码题

### 1. 如何支持任务取消？

**背诵答案：**

我会先在 `TaskStatus` 增加 `CANCELLED`，再在 `TaskStore` 里增加 `mark_cancelled`。同时保存后台 task handle，例如 `thread_id -> asyncio.Task`，新增取消接口时先 `task.cancel()`，runner 捕获 `asyncio.CancelledError` 后更新状态并推送取消事件。

**追问补充：**

当前只存状态，没有保存 task handle。

### 2. 如何把 `task_store` 换成 Redis？

**背诵答案：**

Redis key 可以设计为 `task:{thread_id}` 存 hash，包括 query、status、result、error、session_dir、created_at、updated_at。状态更新用原子写入，必要时加 TTL。WebSocket 历史事件可以用 `task:{thread_id}:events` list 或 stream 存储。

**追问补充：**

多实例必须共享状态。

### 3. 如何支持一个任务多个 WebSocket？

**背诵答案：**

把 `active_connections` 从 `Dict[str, WebSocket]` 改成 `Dict[str, Set[WebSocket]]`。connect 时加入集合，disconnect 时移除连接，集合为空再删除 key。发送时遍历所有连接，失败的连接清理掉。还要考虑并发修改，可以加 lock。

**追问补充：**

生产还要鉴权和心跳。

### 4. 如何给 SQL 自动加 `LIMIT 100`？

**背诵答案：**

不能简单字符串拼接，因为 SQL 可能已有 LIMIT、子查询或尾部分号。最稳妥是使用 SQL parser；MVP 可以在校验通过后判断顶层 SELECT 是否已有 LIMIT，没有则包一层：`SELECT * FROM ({query}) AS t LIMIT 100`。但 SHOW/DESCRIBE 不适合这样包，需要分类型处理。

**追问补充：**

这题考你别乱拼 SQL。

### 5. 如何防止上传文件名攻击？

**背诵答案：**

在 `/api/upload` 保存前对 `file.filename` 做清洗，只允许基础文件名，拒绝包含 `/`、`\`、`..`、控制字符和空文件名；还要限制扩展名和大小。最终路径用 `target_dir / safe_name` 后 resolve，并确认仍在 target_dir 下。

**追问补充：**

和下载目录校验思路一致。

### 6. 如何做断线重连补发？

**背诵答案：**

monitor 每次发事件时，除了 WebSocket 推送，还把事件追加到持久化存储，比如 Redis stream。前端重连时带上 last_event_id，服务端读取该任务之后的事件补发，再恢复实时推送。这样 WebSocket 断开不会丢关键进度。

**追问补充：**

当前 MVP 没做事件持久化。

### 7. 如何加任务超时？

**背诵答案：**

可以在 `_run_task_background` 里用 `asyncio.wait_for(run_deep_agent(...), timeout=settings.task_timeout_sec)`。超时时捕获 `asyncio.TimeoutError`，调用 `task_store.mark_error` 或专门的 timeout 状态，并通过 monitor 推送错误事件。

**追问补充：**

注意清理 ContextVar 和后台任务。

### 8. 如何避免报告覆盖？

**背诵答案：**

在 `generate_markdown` 中生成目标路径后，如果文件已存在，可以追加时间戳或递增编号，比如 `效能周报_1.md`。同时返回最终文件路径给 Agent 和前端。生产中还可以把报告元数据写入任务记录，便于下载和列表展示。

**追问补充：**

当前工具会直接写指定文件名。

## 最推荐背下来的三段话

### 项目亮点

这个项目的亮点是把研发效能分析做成了可运行的 Multi-Agent 系统。它不是简单聊天，而是能查 MySQL 结构化数据、读取上传文件、检索外部实践、分析指标并生成报告。后端用 FastAPI 承接长任务，WebSocket 实时推送子 Agent 和工具执行进度，工具层还做了 SQL 只读和路径隔离。

### 核心难点

核心难点是长任务和多会话隔离。Agent 执行时间不稳定，所以 HTTP 不能阻塞等待。我用 `thread_id` 串起任务状态、WebSocket 推送、LangGraph checkpoint 和输出目录；runner 里用 ContextVar 保存当前会话目录和任务 ID，让工具层在异步并发下安全读写当前任务文件。

### 工程化取舍

这个版本是 MVP，所以任务状态和 checkpoint 都用内存实现，便于本地演示和快速迭代。但安全和扩展边界已经预留：SQL 只读校验、API Key、CORS、上传大小限制、output 路径限制、结构化日志和 RAGFlow stub。生产化时可以把状态迁到 Redis/数据库，引入真实鉴权、任务取消、断线补发和多实例部署。
