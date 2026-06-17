# 结构化讲解规范（nanny-teaching-style）

Agent 讲代码时的**默认文风**。用户未要求「逐行」时，按**模块级 → 方法级**讲解，不默认拆每一行。

## 1. 语气与假设

- 假设用户：能跟读 Python，但 asyncio / WebSocket 可能不熟
- 禁止：「显而易见」「很简单」「众所周知」
- 术语第一次出现给中文别名（如 `payload` = 要发出去的 JSON 消息）
- 用 **你** 称呼用户，用 **我们项目** 指 EfficiencyAgent

## 2. 三种讲解粒度

| 粒度 | 何时用 | 输出形式 |
|------|--------|----------|
| **模块级** | 开讲任何文件 | 总图、分段计划、import 分组、全局单例 |
| **方法级（默认）** | 每个函数、类、路由 | 职责 + 调用链 + 关键代码摘录 + 设计点 |
| **逐行级** | 用户说「逐行/每一行」，或点名某段很难 | 逐行表，每段 ≤25 行 |

**默认路径**：模块总图 → 按逻辑块讲方法 → 全文件串联图 / 面试三句话。  
**不要**：一上来 187 行逐行表；**不要**：import 默认逐行拆。

## 3. 讲一个文件的标准流程

### Step A：30 秒总图（必做）

```markdown
## 📌 [文件名] 总图

**干什么**：[一句话]
**结构**：（按逻辑块，不必抠每一行）
- [块名]：…
**谁调用谁**：[箭头链]
**建议阅读顺序**：块1 → 块2 → …
```

### Step B：分段计划（按逻辑块）

| 段 | 大致行号 | 块名 | 讲完应记住 |
|----|----------|------|------------|
| 1 | 1～21 | 依赖与导入 | 三类 import 各干什么 |
| 2 | 23～37 | App 初始化 | CORS、目录 |
| 3 | 62～84 | 任务提交 | create_task 为何不阻塞 |

行号仅作**导航**，段内用**方法级**讲，不强制每行一行表。

### Step C：import 区（模块级，禁止默认逐行）

**写法示例**：

```markdown
**依赖分组**
- 标准库：`asyncio`（后台任务）、`uuid`（生成 thread_id）
- FastAPI：`Depends`、`WebSocket`、上传与 CORS
- 业务：`run_deep_agent`、`task_store`、`manager`
```

整段 import 用 **1 个小节** 讲完；只有用户问「某个 import 不懂」再展开。

### Step D：方法块（默认主体）

每个 `def` / 类 / `@app.xxx` 一节：

```markdown
### `_start_task`（L69～73）

**干什么**：接单、写 task_store、后台启动 Agent、立刻返回。
**谁调谁**：`create_task` → 本函数 → `task_store.create` + `asyncio.create_task` → `_run_task_background` → `run_deep_agent`
**关键代码**：
（贴 3～8 行）
**设计点**：用 `create_task` 而不是 `await run_deep_agent`，否则 HTTP 阻塞到 Agent 跑完。
**若写错**：await 在 handler 里 → 客户端长时间无响应。
```

- `async`/`await`：在方法块里用 1～2 句说明「等谁、为何不阻塞」即可。
- 类型注解：在**首次出现**的相关方法里顺带解释，不单独为注解逐行开表。

### Step E：逐行表（仅逐行模式或难点）

用户触发「逐行」「每一行过」或指定「细讲 L48～55」时再用：

| 行号 | 代码 | 白话 | 不写/写错会怎样 |
|------|------|------|----------------|
| … | … | … | … |

规则：每段 ≤25 行；空行可不单独占行，合并进相邻逻辑说明。

### Step F：段末小结

- 3 条 bullet 或「面试一句话」
- 大文件可在全文件讲完再给 **串联图 + 自检题**

## 4. 比喻库（按需选用）

| 概念 | 比喻 |
|------|------|
| ConnectionManager | 快递站地址簿 |
| thread_id | 快递单号，全链路同一个号 |
| WebSocket | 电话一直通着 |
| HTTP POST 立即返回 | 前台收单给回执，厨房后台做菜 |
| task_store | 订单状态牌 |
| monitor | 厨房广播 |

每个逻辑块 **至多 1 个比喻**，不堆砌。

## 5. 完整示例对比

### ❌ 默认不要（import 逐行）

| 行号 | 代码 | 白话 | … |
| 7 | import asyncio | … | … |
| 8 | import uuid | … | … |
| （每个 import 一行） | | | |

### ✅ 默认要（模块 + 方法）

**导入（分组）**：asyncio + uuid 管后台任务和会话 ID；FastAPI 管路由；`run_deep_agent` / `task_store` / `manager` 是业务三角。

**`_start_task`**：先 `create` 再 `asyncio.create_task`，HTTP 立即返回 `started`；真正状态变迁在 runner 里 `mark_running` → `mark_done`。

## 6. 用户说「讲 xxx.py」

1. 输出 **Step A + B**（总图 + 逻辑分段表）
2. 按块 **Step C（import 分组）+ Step D（方法块）** 连续讲
3. 小文件可一轮讲完；大文件每轮 2～4 个方法块
4. 结尾：**串联图** + 2～3 道自检题
5. 仅当用户说「逐行」→ 切换到 **Step E**

## 7. 与「禁止贴长代码」的关系

- **讲解已有代码**：方法级摘录 + 调用链；全文粘贴仅在逐行模式
- **生成新代码**：禁止无结构的长代码；须先例子再实现

## 8. 推荐逻辑分段（EfficiencyAgent）

### monitor.py

| 块 | 内容 |
|----|------|
| ToolMonitor 单例 + set_websocket_manager | 全局一个 monitor |
| _emit | 拼 payload、跨协程发 WS |
| report_* | 四个上报入口 |
| ConnectionManager | connect / disconnect / send_to_thread |
| 全局 monitor / manager | 谁 import 谁 |

### task_store.py

| 块 | 内容 |
|----|------|
| TaskStatus + __init__ | 状态机与锁 |
| create / get | 建单与查询 |
| _update + mark_* | 状态变迁 API |
| task_store 单例 | 与 server / runner 分工 |

### server.py

| 块 | 内容 |
|----|------|
| app 初始化 + CORS + 目录 | 启动准备 |
| verify_api_key + 模型 | 鉴权与入参 |
| startup + 任务提交 | set_loop、create_task 后台跑 |
| GET 任务 / 上传 / 下载 | 辅助 API |
| WebSocket + health | 进度通道与探活 |

讲具体文件时默认按上表分块；用户可指定「只讲任务提交那块」。
