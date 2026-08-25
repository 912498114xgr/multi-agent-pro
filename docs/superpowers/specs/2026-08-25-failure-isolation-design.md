# R1 失败隔离设计（已批准执行）

## 目标

工具软失败不打断图；结果结构化；经 ContextVar 收集失败步骤；任务结束按 critical/optional 决策 → `done` / `partial_success` / `error`。

## 为何用 ContextVar 收集器

子 Agent 内工具结果不会原样出现在主 Agent 的 `tools` 节点；仅在 runner 里解析 astream **会漏掉** DB/Tavily 失败。工具在 `format_error` 时写入当前协程的失败列表，runner 结束时读取。

## 协议

```
[[EA_TOOL_RESULT]]{"ok":false,"tool":"internet_search","role":"optional","error_type":"config_missing","retryable":false,"message":"..."}\n
<供模型阅读的正文>
```

成功同样带 `ok:true` + 正文数据。

## 角色

| role | 工具 |
|------|------|
| critical | list_sql_tables, get_table_data, execute_sql_query, read_file_content, generate_markdown |
| optional | internet_search, get_assistant_list, create_ask_delete, convert_md_to_pdf |

## 决策

- 存在 critical 失败 → `error`（写入 failed_steps）
- 仅 optional 失败 → `partial_success`
- 无失败 → `done`
- 未捕获异常 → 仍 `error`（现有路径）

## 文件

- `tools/tool_result.py` — 协议与决策
- `context/failure_steps.py` — 收集器
- `api/task_store.py` — PARTIAL_SUCCESS
- `tools/*.py` — 包装返回值
- `agent/mainagent/runner.py` — 结束决策
- `api/monitor.py` — step_failed / degraded
- `prompt/prompts.yml` — 对齐策略
- `tests/test_tool_result.py` 等
