"""R6 单测辅助：关闭 store/checkpointer 并恢复 memory 实现。"""

from __future__ import annotations

import asyncio
import importlib
import os


def close_and_restore_task_store() -> None:
    try:
        import api.task_store as ts_mod

        if hasattr(ts_mod.task_store, "close"):
            ts_mod.task_store.close()
    except Exception:
        pass

    os.environ["TASK_STORE_BACKEND"] = "memory"
    os.environ.pop("AGENT_DATABASE_URL", None)
    from config.settings import get_settings

    get_settings.cache_clear()
    import api.server as server_mod

    importlib.reload(ts_mod)
    importlib.reload(server_mod)
    os.environ.pop("TASK_STORE_BACKEND", None)
    get_settings.cache_clear()

    try:
        from agent.checkpointer import close_checkpointer, reset_checkpointer_for_tests
        from agent.mainagent.runner import reset_main_agent_for_tests

        asyncio.run(close_checkpointer())
        reset_checkpointer_for_tests()
        reset_main_agent_for_tests()
    except Exception:
        pass
