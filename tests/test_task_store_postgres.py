"""R6b: Postgres TaskStore persistence."""

from __future__ import annotations

import os
import unittest

from api.task_store import TaskStatus
from api.task_store_postgres import PostgresTaskStore


@unittest.skipUnless(
    os.getenv("TEST_AGENT_DATABASE_URL"),
    "需要 TEST_AGENT_DATABASE_URL（或本地 docker compose postgres）",
)
class PostgresTaskStoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._url = os.environ["TEST_AGENT_DATABASE_URL"]
        cls.store = PostgresTaskStore(cls._url)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.store.close()

    def test_create_and_get(self) -> None:
        tid = "pg-test-001"
        self.store.create(tid, "hello pg")
        self.store.mark_running(tid)
        task = self.store.get(tid)
        assert task is not None
        self.assertEqual(task["status"], TaskStatus.RUNNING.value)
        self.assertEqual(task["query"], "hello pg")

    def test_list_tasks_order(self) -> None:
        self.store.create("pg-a", "a")
        self.store.create("pg-b", "b")
        self.store.mark_running("pg-b")
        listed = self.store.list_tasks(limit=10)
        ids = [t["thread_id"] for t in listed if t["thread_id"] in ("pg-a", "pg-b")]
        if len(ids) >= 2:
            self.assertEqual(ids[0], "pg-b")


if __name__ == "__main__":
    unittest.main()
