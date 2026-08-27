"""
R6b：LangGraph checkpointer 工厂 — 默认 AsyncPostgresSaver；单测可 memory。
"""

from __future__ import annotations

import asyncio
import sys
import threading
from contextlib import AbstractAsyncContextManager
from typing import Any, Optional

from config.settings import get_settings

_checkpointer: Optional[Any] = None
_checkpointer_cm: Optional[AbstractAsyncContextManager[Any]] = None
_checkpointer_lock = threading.Lock()
_initialized = False


async def init_checkpointer() -> None:
    """应用 startup 时调用：创建并 setup checkpointer 单例。"""
    global _checkpointer, _checkpointer_cm, _initialized
    with _checkpointer_lock:
        if _initialized:
            return
        settings = get_settings()
        backend = settings.checkpointer_backend.lower()

        if backend == "memory":
            from langgraph.checkpoint.memory import InMemorySaver

            _checkpointer = InMemorySaver()
            _checkpointer_cm = None
            _initialized = True
            return

        if backend == "postgres":
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

            loop = asyncio.get_running_loop()
            if sys.platform == "win32" and "ProactorEventLoop" in type(loop).__name__:
                raise RuntimeError(
                    "Windows 上 psycopg 异步不支持 ProactorEventLoop。"
                    "请改用: python run_api.py"
                    "  或: uvicorn api.server:app --loop api.loop_factory:selector_loop"
                )

            db_url = settings.require_agent_database_url()
            _checkpointer_cm = AsyncPostgresSaver.from_conn_string(db_url)
            _checkpointer = await _checkpointer_cm.__aenter__()
            await _checkpointer.setup()
            _initialized = True
            return

        raise ValueError(f"未知 CHECKPOINTER_BACKEND: {backend}")


async def close_checkpointer() -> None:
    """应用 shutdown 或单测 teardown 时释放连接。"""
    global _checkpointer, _checkpointer_cm, _initialized
    with _checkpointer_lock:
        if _checkpointer_cm is not None:
            await _checkpointer_cm.__aexit__(None, None, None)
        _checkpointer_cm = None
        _checkpointer = None
        _initialized = False


def get_checkpointer():
    """返回已初始化的 checkpointer（需先 await init_checkpointer()）。"""
    if not _initialized or _checkpointer is None:
        raise RuntimeError(
            "checkpointer 未初始化。请确保 FastAPI lifespan 已调用 init_checkpointer()，"
            "或单测中显式 await init_checkpointer()。"
        )
    return _checkpointer


async def checkpoint_exists(thread_id: str) -> bool:
    """Resume 前判断该 thread 是否已有 LangGraph checkpoint。"""
    try:
        cp = get_checkpointer()
        config = {"configurable": {"thread_id": thread_id}}
        if hasattr(cp, "aget_tuple"):
            return await cp.aget_tuple(config) is not None
        if hasattr(cp, "aget"):
            return await cp.aget(config) is not None
        if hasattr(cp, "get_tuple"):
            return cp.get_tuple(config) is not None
        if hasattr(cp, "get"):
            return cp.get(config) is not None
    except RuntimeError:
        raise
    except Exception:
        return False
    return False


def reset_checkpointer_for_tests() -> None:
    """单测同步重置标记（配合 await close_checkpointer() 使用）。"""
    global _checkpointer, _checkpointer_cm, _initialized
    with _checkpointer_lock:
        _checkpointer_cm = None
        _checkpointer = None
        _initialized = False
