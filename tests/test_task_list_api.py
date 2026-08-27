"""R6: GET /api/tasks 会话列表 API。"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


class TaskListApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        os.environ["TASK_STORE_BACKEND"] = "memory"
        os.environ["CHECKPOINTER_BACKEND"] = "memory"
        from config.settings import get_settings

        get_settings.cache_clear()
        import importlib
        import api.server as server_mod
        import api.task_store as ts_mod

        importlib.reload(ts_mod)
        importlib.reload(server_mod)
        self.server = server_mod
        self.client = TestClient(server_mod.app)
        self.headers = {"X-API-Key": "dev-api-key"}

    def tearDown(self) -> None:
        from tests.r6_test_utils import close_and_restore_task_store

        os.environ.pop("TASK_STORE_DB_PATH", None)
        os.environ.pop("CHECKPOINTER_BACKEND", None)
        close_and_restore_task_store()
        self._tmpdir.cleanup()

    def test_list_tasks_returns_summaries(self) -> None:
        self.server.task_store.create("t1", "hello world")
        self.server.task_store.mark_done("t1", "ok")

        res = self.client.get("/api/tasks", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(len(body["tasks"]), 1)
        item = body["tasks"][0]
        self.assertEqual(item["thread_id"], "t1")
        self.assertEqual(item["query"], "hello world")
        self.assertEqual(item["status"], "done")
        self.assertIn("resumable", item)

    def test_get_task_includes_resumable(self) -> None:
        self.server.task_store.create("t2", "q")
        with patch.object(self.server, "checkpoint_exists", new=AsyncMock(return_value=True)):
            self.server.task_store.mark_cancelled("t2")
            res = self.client.get("/api/tasks/t2", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["resumable"])


if __name__ == "__main__":
    unittest.main()
