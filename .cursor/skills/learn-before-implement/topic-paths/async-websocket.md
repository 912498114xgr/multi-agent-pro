# 专题：asyncio + WebSocket（通用）

学完再读用户仓库里**实际的** server / handler / gateway 文件。  
示例用中性命名（`app`、`connection_manager`），**不要**假定文件名。

每步走完过来人拆解 ①～⑥；过关再下一步。

## 1. 同步 vs 异步

| 项 | 内容 |
|----|------|
| 问题 | 长任务不能阻塞整个服务 |
| 官方 | 所用语言的 async 总览 |
| 小实验 | 阻塞 sleep vs 异步 sleep |
| 对照 | 用户文件中的 `async def` / `stream` 入口 |
| 追问 | 为何用流式而不是一次性返回？ |

## 2. 协程、await、事件循环

| 项 | 内容 |
|----|------|
| 问题 | Web 框架跑在事件循环上 |
| 官方 | coroutine、event loop |
| 小实验 | 最小 `asyncio.run(main())` |
| 对照 | 启动钩子里 `get_running_loop()` 一类代码 |
| 追问 | 为何不能在 import 时取 loop？ |

## 3. 后台长任务（先返回 HTTP）

| 项 | 内容 |
|----|------|
| 问题 | 提交任务要立即返回 ID |
| 官方 | create_task / BackgroundTasks / 队列 |
| 小实验 | `create_task(job)` 后立刻 print returned |
| 对照 | 用户仓库里「POST 后立即 return」的那段 |
| 改坏实验 | handler 里 `await` 长任务会怎样？ |

## 4. HTTP vs WebSocket

| 项 | 内容 |
|----|------|
| 问题 | 实时进度不想高频轮询 |
| 官方 | MDN WebSocket；框架 WS 文档 |
| 小实验 | 画轮询 vs 长连接 push |
| 对照 | 为何需要「过程推送」+「终态查询」两套通道（若有） |
| 追问 | 终态用 HTTP、过程用 WS，为何拆分？ |

## 5. 最小 WebSocket Echo

| 项 | 内容 |
|----|------|
| 官方 | 框架 WS 教程 |
| 小实验 | 独立 echo 服务 |
| 对照 | 用户仓库的 WS 路由 |
| 追问 | accept / handshake 在干什么？ |

## 6. 连接表（ID → socket）

| 项 | 内容 |
|----|------|
| 问题 | 多客户端不能串消息 |
| 小实验 | 两个 key 两个字典项 |
| 对照 | connect / disconnect / send_to_id |
| 改坏实验 | 全局单连接会怎样？ |

## 7. 跨线程/跨 loop 发消息（若项目有）

| 项 | 内容 |
|----|------|
| 问题 | 非 WS 协程里如何安全 send |
| 官方 | run_coroutine_threadsafe 等 |
| 对照 | 用户仓库里 `_emit` / `publish` 一类函数 |
| 追问 | loop 用错会报什么？ |

## 8. 闭卷串联

用户口述（不看代码）从「客户端提交」到「收到推送」的路径，Agent 对照**当前仓库**真实符号批改。
