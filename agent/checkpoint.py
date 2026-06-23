"""
LangGraph checkpointer 工厂：有 REDIS_URL 时用 RedisSaver，否则 InMemorySaver。
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from config.settings import get_settings

_checkpointer: Any = None


def _ttl_config(settings) -> dict | None:
    if settings.redis_checkpoint_ttl_sec <= 0:
        return None
    # RedisSaver TTL 单位为分钟
    return {"default_ttl": max(1, settings.redis_checkpoint_ttl_sec // 60)}


@lru_cache
def get_checkpointer():
    """返回进程级单例 checkpointer（首次调用时初始化 Redis 索引）。"""
    settings = get_settings()
    if settings.redis_url:
        from langgraph.checkpoint.redis import RedisSaver

        saver = RedisSaver(redis_url=settings.redis_url, ttl=_ttl_config(settings))
        saver.setup()
        return saver

    from langgraph.checkpoint.memory import InMemorySaver

    return InMemorySaver()


def init_checkpointer():
    """FastAPI startup 时显式初始化（创建 Redis 索引）。"""
    global _checkpointer
    _checkpointer = get_checkpointer()
    return _checkpointer
