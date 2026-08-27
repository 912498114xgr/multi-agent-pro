"""R6: POST /api/tasks/{id}/resume."""

from __future__ import annotations

import asyncio
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from tests.r6_test_utils import close_and_restore_task_store


class TaskResumeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        os.environ["TASK_STORE_BACKEND"] = "memory"
        os.environ["CHECKPOINTER_BACKEND"] = "memory"
        from config.settings import get_settings

        get_settings.cache_clear()

    def tearDown(self) -> None:
        os.environ.pop("TASK_STORE_DB_PATH", None)
        os.environ.pop("CHECKPOINTER_BACKEND", None)
        close_and_restore_task_store()
        self._tmpdir.cleanup()

    def test_resume_not_found(self) -> None:
        import importlib

        import api.server as server_mod
        import api.task_store as ts_mod

        importlib.reload(ts_mod)
        importlib.reload(server_mod)

        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(server_mod.resume_task("missing"))
        self.assertEqual(ctx.exception.status_code, 404)

    def test_resume_done_rejected(self) -> None:
        import importlib

        import api.server as server_mod
        import api.task_store as ts_mod

        importlib.reload(ts_mod)
        importlib.reload(server_mod)

        ts_mod.task_store.create("done-id", "q")
        ts_mod.task_store.mark_done("done-id", "ok")

        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(server_mod.resume_task("done-id"))
        self.assertEqual(ctx.exception.status_code, 409)

    def test_resume_schedules_when_checkpoint_exists(self) -> None:
        import importlib

        import api.server as server_mod
        import api.task_store as ts_mod

        importlib.reload(ts_mod)
        importlib.reload(server_mod)

        ts_mod.task_store.create("err-id", "q")
        ts_mod.task_store.mark_error("err-id", "fail")

        with patch.object(server_mod, "checkpoint_exists", new=AsyncMock(return_value=True)):
            with patch.object(server_mod, "_schedule_agent_task") as mock_sched:
                result = asyncio.run(server_mod.resume_task("err-id"))
        self.assertEqual(result["status"], "resumed")
        mock_sched.assert_called_once_with("q", "err-id")
        task = ts_mod.task_store.get("err-id")
        assert task is not None
        self.assertEqual(task["status"], "running")


if __name__ == "__main__":
    unittest.main()
