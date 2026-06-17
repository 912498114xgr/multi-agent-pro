# 官方参考索引

讲解时 **必须先链此处**，再映射项目代码。优先中文文档，英文为辅。

## Python asyncio

| 知识点 | 链接 | 阅读重点 |
|--------|------|----------|
| asyncio 总览 | https://docs.python.org/zh-cn/3/library/asyncio.html | 协程、事件循环概念 |
| 协程与 await | https://docs.python.org/zh-cn/3/glossary.html#term-coroutine | 什么是协程 |
| asyncio.run | https://docs.python.org/zh-cn/3/library/asyncio-runner.html#asyncio.run | 程序入口 |
| create_task | https://docs.python.org/zh-cn/3/library/asyncio-task.html#asyncio.create_task | 并发调度任务 |
| Task 对象 | https://docs.python.org/zh-cn/3/library/asyncio-task.html#asyncio.Task | 任务生命周期 |
| 事件循环 | https://docs.python.org/zh-cn/3/library/asyncio-eventloop.html | get_running_loop |
| 多线程与 asyncio | https://docs.python.org/zh-cn/3/library/asyncio-dev.html#asyncio-multithreading | run_coroutine_threadsafe |
| run_coroutine_threadsafe | https://docs.python.org/zh-cn/3/library/asyncio-task.html#asyncio.run_coroutine_threadsafe | 跨线程投递协程 |

## FastAPI / Starlette

| 知识点 | 链接 | 阅读重点 |
|--------|------|----------|
| 第一个 API | https://fastapi.tiangolo.com/zh/ | 路由基础 |
| 后台任务 BackgroundTasks | https://fastapi.tiangolo.com/zh/tutorial/background-tasks/ | 对比 create_task 选型 |
| WebSocket | https://fastapi.tiangolo.com/zh/advanced/websockets/ | accept / receive / send |
| 更大的应用结构 | https://fastapi.tiangolo.com/zh/tutorial/bigger-applications/ | 模块拆分 |

## 概念层（HTTP vs WebSocket）

| 知识点 | 链接 | 阅读重点 |
|--------|------|----------|
| WebSocket API | https://developer.mozilla.org/zh-CN/docs/Web/API/WebSocket | 长连接、全双工 |
| HTTP 请求响应 | https://developer.mozilla.org/zh-CN/docs/Web/HTTP | 短连接、轮询对比 |

## LangChain / DeepAgents（项目 Phase 4）

| 知识点 | 链接 | 阅读重点 |
|--------|------|----------|
| LangGraph streaming | https://langchain-ai.github.io/langgraph/how-tos/streaming/ | astream chunk 结构 |
| init_chat_model | https://python.langchain.com/docs/integrations/chat/ | base_url 传参 |

## EfficiencyAgent 项目内文档

| 文档 | 路径（相对 multi-agent-pro 根） |
|------|--------------------------------|
| Phase 5 总览 | `docs/Phase5-新增模块学习指南.md` |
| 各模块说明 | `docs/modules/01-llm-model.md` … `07-runner-改造.md` |
| 参考实现 | 同级目录 `deep_search_pro/api/server.py` |

## 推荐阅读顺序（Phase 5 零基础）

1. MDN WebSocket（知道和 HTTP 区别）
2. asyncio 总览 → coroutine → asyncio.run
3. create_task
4. FastAPI WebSocket 教程（跟做 echo 示例）
5. asyncio 多线程节（理解 run_coroutine_threadsafe）
6. 打开项目 `api/server.py`、`api/monitor.py` 做过来人拆解
