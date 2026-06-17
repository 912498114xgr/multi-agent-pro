# 01 — `llm/model.py`：LLM 连接稳定化

## 这是什么？

加载大语言模型（LLM）单例的模块。`runner.py` 和 DeepAgents 通过 `from llm.model import model` 使用它。

## 为什么改？

Phase 4 版本大致是这样：

```python
os.environ.setdefault("OPENAI_BASE_URL", ...)
init_chat_model(model=..., model_provider="openai")
```

常见问题：

1. **只设环境变量**：LangChain 有时读不到 `OPENAI_BASE_URL`，仍请求官方 `api.openai.com`
2. **Windows 系统代理**：`httpx` 默认 `trust_env=True`，走代理后经常出现 `Connection error`
3. **无超时控制**：网络卡住时一直挂起

## 改了什么？

```python
def _build_http_clients(timeout_sec: float):
    return (
        httpx.Client(trust_env=False, timeout=timeout_sec),
        httpx.AsyncClient(trust_env=False, timeout=timeout_sec),
    )

init_chat_model(
    model=settings.openai_model,
    model_provider="openai",
    base_url=settings.openai_base_url,      # 显式传入
    api_key=settings.openai_api_key or None,
    http_client=http_client,                # 同步客户端
    http_async_client=http_async_client,    # 异步客户端（astream 用这个）
)
```

| 参数 | 作用 |
|------|------|
| `base_url` | 指向 edgefn / 百炼等兼容 OpenAI 的中转地址 |
| `trust_env=False` | 忽略系统 HTTP_PROXY，直连 API |
| `timeout` | 从 `OPENAI_TIMEOUT_SEC` 读取，默认 120 秒 |

## 在项目中的位置

```
.env (OPENAI_*)
    ↓
config/settings.py
    ↓
llm/model.py  →  model 单例
    ↓
agent/mainagent/runner.py  →  create_deep_agent(model=model, ...)
```

## 如何验证

1. `.env` 配置正确的 `OPENAI_BASE_URL` / `OPENAI_API_KEY` / `OPENAI_MODEL`
2. 运行 `python agent/test_run.py`
3. 若仍 Connection error：换网络、换中转、检查 Key 额度

## 学习要点

- **单例模式**：全进程共用一个 `model`，避免重复建连接
- **同步 + 异步客户端都要传**：DeepAgents 的 `astream` 走异步 HTTP
- 这是「基建层」问题，与 Agent 业务逻辑无关，但不通则整个系统跑不起来
