"""R6: duplicate create on running thread returns 409."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from tests.r6_test_utils import close_and_restore_task_store


class TaskIdempotencyTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        os.environ["TASK_STORE_BACKEND"] = "memory"
        os.environ.pop("TASK_STORE_DB_PATH", None)
        os.environ["CHECKPOINTER_BACKEND"] = "memory"
        from config.settings import get_settings

        get_settings.cache_clear()

    def tearDown(self) -> None:
        os.environ.pop("TASK_STORE_DB_PATH", None)
        os.environ.pop("CHECKPOINTER_BACKEND", None)
        close_and_restore_task_store()
        self._tmpdir.cleanup()

    def test_running_thread_rejected(self) -> None:
        import importlib

        import api.server as server_mod
        import api.task_store as ts_mod

        importlib.reload(ts_mod)
        importlib.reload(server_mod)

        ts_mod.task_store.create("dup-id", "q")
        ts_mod.task_store.mark_running("dup-id")

        from api.server import TaskRequest, _start_task

        with patch.object(server_mod, "_schedule_agent_task"):
            with self.assertRaises(HTTPException) as ctx:
                _start_task(TaskRequest(query="again", thread_id="dup-id"))
        self.assertEqual(ctx.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
