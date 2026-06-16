import httpx
from langchain.chat_models import init_chat_model

from config.settings import get_settings

# Windows 系统代理常导致 httpx 走代理后 ConnectError；直连 API 更可靠
_HTTP_CLIENT = httpx.Client(trust_env=False, timeout=120.0)
_HTTP_ASYNC_CLIENT = httpx.AsyncClient(trust_env=False, timeout=120.0)


def get_model():
    """从 config.settings 加载 LLM 实例。"""
    settings = get_settings()
    return init_chat_model(
        model=settings.openai_model,
        model_provider="openai",
        base_url=settings.openai_base_url,
        api_key=settings.openai_api_key or None,
        http_client=_HTTP_CLIENT,
        http_async_client=_HTTP_ASYNC_CLIENT,
    )


# 模块级单例，供 runner 导入
model = get_model()
