import httpx
from langchain.chat_models import init_chat_model

from config.settings import get_settings

def _build_http_clients(timeout_sec: float):
    # Windows 系统代理常导致 httpx 走代理后 ConnectError；直连 API 更可靠
    return (
        httpx.Client(trust_env=False, timeout=timeout_sec),
        httpx.AsyncClient(trust_env=False, timeout=timeout_sec),
    )


def get_model():
    """从 config.settings 加载 LLM 实例（显式 base_url，避免仅依赖环境变量）。"""
    settings = get_settings()
    http_client, http_async_client = _build_http_clients(float(settings.openai_timeout_sec))
    return init_chat_model(
        model=settings.openai_model,
        model_provider="openai",
        base_url=settings.openai_base_url,
        api_key=settings.openai_api_key or None,
        http_client=http_client,
        http_async_client=http_async_client,
    )


# 模块级单例，供 runner 导入
model = get_model()
