"""TaskStore partial_success and failed_steps."""

from __future__ import annotations

import unittest

from api.task_store import TaskStatus, TaskStore


class TaskStorePartialTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = TaskStore()

    def test_mark_partial_success_sets_status_and_steps(self) -> None:
        self.store.create("t1", "query")
        self.store.mark_running("t1")
        steps = [{"tool": "internet_search", "role": "optional", "message": "down", "error_type": "upstream"}]
        record = self.store.mark_partial_success(
            "t1",
            result="周报已生成（行业实践缺失）",
            session_dir="/tmp/s",
            failed_steps=steps,
        )
        assert record is not None
        self.assertEqual(record["status"], TaskStatus.PARTIAL_SUCCESS.value)
        self.assertEqual(record["failed_steps"], steps)
        self.assertEqual(record["result"], "周报已生成（行业实践缺失）")

    def test_mark_error_can_attach_failed_steps(self) -> None:
        self.store.create("t2", "query")
        steps = [{"tool": "list_sql_tables", "role": "critical", "message": "db", "error_type": "upstream"}]
        record = self.store.mark_error("t2", "critical tool failed", failed_steps=steps)
        assert record is not None
        self.assertEqual(record["status"], TaskStatus.ERROR.value)
        self.assertEqual(record["failed_steps"], steps)

    def test_mark_done_clears_failed_steps(self) -> None:
        self.store.create("t3", "query")
        record = self.store.mark_done("t3", "ok", session_dir="/tmp/x")
        assert record is not None
        self.assertEqual(record["status"], TaskStatus.DONE.value)
        self.assertEqual(record["failed_steps"], [])


if __name__ == "__main__":
    unittest.main()
