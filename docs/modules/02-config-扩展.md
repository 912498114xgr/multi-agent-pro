# 02 — `config/settings.py` 扩展项

## 这是什么？

项目统一配置中心（Phase 3 已有）。Phase 5 只**新增两个字段**，不新建文件。

## 新增字段

| 配置项 | 环境变量 | 默认值 | 用途 |
|--------|----------|--------|------|
| `openai_timeout_sec` | `OPENAI_TIMEOUT_SEC` | `120` | LLM HTTP 请求超时（秒） |
| `runner_debug` | `RUNNER_DEBUG` | `False` | 是否打印 astream 全量 chunk |

`.env` 示例：

```env
OPENAI_TIMEOUT_SEC=120
RUNNER_DEBUG=0
```

`RUNNER_DEBUG=1` 时开启深度调试（等价于 Python 里 `runner_debug=True`）。

## 为什么需要？

### `openai_timeout_sec`

- Agent 多轮调用子 Agent，单次 LLM 可能较慢
- 有明确超时才能快速失败，而不是无限等待
- 与 `task_timeout_sec`（整任务 600 秒）是不同层级：一个是单次 HTTP，一个是整任务

### `runner_debug`

- 开发时需要看 `chunk` / `state` / `messages` 全量内容
- 正常运行时这些输出会淹没 `[Monitor:xxx]` 业务日志
- **用配置开关**，而不是注释/删代码

## 在项目中的位置

```
.env
  ↓
get_settings()  ← 全项目唯一读取入口
  ↓
├── llm/model.py        → openai_timeout_sec
├── agent/.../runner.py → runner_debug
└── api/server.py       → api_key, cors_origins, max_upload_mb ...
```

## 学习要点

- **pydantic-settings**：字段名 `runner_debug` 自动映射 `RUNNER_DEBUG`
- **@lru_cache**：改 `.env` 后需重启进程才生效
- 企业项目习惯：调试行为走配置，不走改代码
