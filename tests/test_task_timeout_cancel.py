"""R3: task timeout / cancelled 状态与 store。"""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from api.task_store import TaskStatus, TaskStore


class TaskStoreTimeoutCancelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = TaskStore()
        self.store.create("t1", "hello")

    def test_mark_timeout(self) -> None:
        self.store.mark_running("t1")
        self.store.mark_timeout("t1", error="too slow")
        task = self.store.get("t1")
        self.assertEqual(task["status"], TaskStatus.TIMEOUT.value)
        self.assertEqual(task["error"], "too slow")

    def test_mark_cancelled(self) -> None:
        self.store.mark_running("t1")
        self.store.mark_cancelled("t1")
        task = self.store.get("t1")
        self.assertEqual(task["status"], TaskStatus.CANCELLED.value)


class WaitForTimeoutTests(unittest.IsolatedAsyncioTestCase):
    async def test_wait_for_marks_timeout(self) -> None:
        import importlib
        import os

        os.environ["TASK_STORE_BACKEND"] = "memory"
        os.environ["CHECKPOINTER_BACKEND"] = "memory"
        from config.settings import get_settings

        get_settings.cache_clear()
        import api.task_store as ts_mod
        import api.server as server

        importlib.reload(ts_mod)
        importlib.reload(server)

        tid = "timeout-demo"
        server.task_store.create(tid, "q")
        server.task_store.mark_running(tid)

        async def _slow(*_a, **_k):
            await asyncio.sleep(10)

        with patch.object(server, "run_deep_agent", new=_slow):
            with patch.object(server._settings, "task_timeout_sec", 0.05):
                await server._run_task_background("q", tid)

        task = server.task_store.get(tid)
        self.assertEqual(task["status"], "timeout")
        self.assertIn("task_timeout_sec", task["error"] or "")


class CancelApiLogicTests(unittest.IsolatedAsyncioTestCase):
    async def test_cancel_running_task(self) -> None:
        import importlib
        import os

        os.environ["TASK_STORE_BACKEND"] = "memory"
        os.environ["CHECKPOINTER_BACKEND"] = "memory"
        from config.settings import get_settings

        get_settings.cache_clear()
        import api.task_store as ts_mod
        import api.server as server

        importlib.reload(ts_mod)
        importlib.reload(server)

        tid = "cancel-demo"
        server.task_store.create(tid, "q")
        server.task_store.mark_running(tid)

        started = asyncio.Event()

        async def _hang(*_a, **_k):
            started.set()
            await asyncio.sleep(30)

        with patch.object(server, "run_deep_agent", new=_hang):
            with patch.object(server._settings, "task_timeout_sec", 60):
                bg = asyncio.create_task(server._run_task_background("q", tid))
                server._running_tasks[tid] = bg
                await started.wait()
                bg.cancel()
                try:
                    await bg
                except asyncio.CancelledError:
                    pass

        task = server.task_store.get(tid)
        self.assertEqual(task["status"], "cancelled")


if __name__ == "__main__":
    unittest.main()
