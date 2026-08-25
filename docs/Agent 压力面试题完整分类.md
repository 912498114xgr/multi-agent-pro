# Agent 压力面试题完整分类

## 一、工具调用 & 失败处理

> 高频连环追问区：失败是否幻觉、重试、超时、partial、谁决定继续

1. 中间某步失败了，怎么继续？✅ 工具软失败不抛，保图继续；critical/optional + decide_task_status → error / partial_success / done；继续与否由**任务层代码**定（R1）
2. 可选失败后会不会幻觉补数据？✅ Prompt 禁止补齐 + 结构化错误；**R1b 成稿门禁**：已有 critical 失败时 `generate_markdown` 拒写充实报告
3. 同一工具失败为何还调两次？重试策略是什么？✅ Trace 可见；`retryable=false` 时 **R1b 代码短路**（`short_circuited_retry`），不二次连库
4. 工具 / 模型超时怎么做？✅ 三层：LLM HTTP=`openai_timeout_sec`；整任务=`task_timeout_sec` 已 `wait_for`；取消=`POST .../cancel`（R3）
5. 超时后状态？Context 清不清？✅ 状态 `timeout` / `cancelled`；runner `finally` reset Trace/failure/retry/session ContextVar（R3）
6. partial 后能否只重试失败步？❌ 未做。设计：`POST .../retry` 按 failed_steps 仅重跑 optional；需新 run_id。当前可新开任务或改 query 重跑
7. 谁决定继续？模型还是代码？✅ **代码**：`decide_task_status`；模型可能仍想重试/写稿，靠 R1b 闸挡住
8. optional 失败后如何禁止假数据补齐？critical 为何还能写长报告？✅ optional：Prompt + 禁止补造；critical：成稿门禁拒写盘；终态仍可为 error，说明性 `model_result` 允许、充实假 md 不允许

## 二、任务生命周期｜状态管理｜持久化｜并发

> 任务暂停恢复、重启丢失、幂等、多实例、子 Agent 并行

1. 任务暂停 / 恢复怎么做？❌无人工暂停；TaskStore 内存；设计用 checkpointer + turn 边界恢复 R6
2. 进程重启任务还在吗？❌内存 TaskStore，重启丢失；升级 SQLite/RedisR6
3. 连点两次发送会怎样？⚠️新 thread_id 或同会话再跑；无严格幂等锁，承认并发控制弱幂等 / 锁
4. 多实例下 ContextVar 够吗？✅/⚠️单进程协程够用；多实例要外置状态 + 分布式 trace 架构口述
5. 多个子 Agent 能否并行？共享文件系统会不会互相覆盖？

## 三、可观测性｜Trace｜WS｜Monitor｜OpenTelemetry｜成本 SLA

> TraceID、OTel、意图节点、子 Agent 嵌套、WS 与 Trace 区别、日志双计、成本 SLA

1. 全链路追踪 ID 怎么设计？⚠️现有 thread_id（会话 / 任务）+ session trace.json 步骤序；不是 OTel trace_id/span_idR2
2. OpenTelemetry？token / 成本？❌了解概念：task/run/span 三级 + 用量钩子；项目未接入；勿说已打通观测升级
3. 为何 Trace 没有「意图识别」？✅无独立意图节点；意图折叠在主模型 tool_calls（如 task）；委派理由在 description 规划事件可选
4. 子 Agent 工具主图为何看不到？✅嵌套子图 chunk 不进主 astream；用 ContextVar + hooks/format_* 记账（R2 动机）R2 已做
5. 进度 WS 和 Trace 啥区别？✅WS：实时精简；Trace：事后完整（成败 + 耗时）；不全推工具结果防刷屏 R2 已做
6. 日志 / Monitor / Trace 会不会双计？⚠️分工：Monitor 进度、Trace 步骤真相、日志排障；未做统一 span 关联观测统一
7. 成本与 SLA 怎么看？❌无 token 聚合与告警；设计按 task / 子 Agent 聚合 duration + 用量成本观测

## 四、输出质量｜报告溯源

> 报告溯源、失败态仍输出长 markdown 问题

1. 报告不准，有溯源吗？❌无段落级 citation；只能承认靠 Prompt + 失败降级，未做证据绑定 R8 / 最小引用
2. 关键失败为何还有长 Markdown？✅ 说明性 model_result 允许；**充实假 md 被 R1b 成稿门禁拒写**；终态仍为 error（正文≠成功）

## 五、安全风险

> 文件路径逃逸、SQL 注入、Prompt Injection

1. 上传 ../、路径逃逸？❌上传未 Path.name 消毒；沙箱未强制 is_relative_toR4
2. SQL 写操作 / 注入？⚠️有只读向校验器；纵深靠只读账号 + 行数限制，安全未闭环 R4
3. Prompt injection（上传文件攻击）？❌未做专用防护；可讲输入隔离与工具沙箱方向安全 / R4

## 六、测试质量保障

1. 怎么证明失败策略没回归？❌有单元测试（工具协议 / Trace）；缺失败向端到端 Eval（例子 A/B）R5

## 七、架构 & 产品化拔高题

1. 和状态机工作流比，Agent 不确定性如何产品化？✅用显式终态 + Trace + 降级，把不确定收敛成可解释结果；不假装确定性 DAG 口述加分