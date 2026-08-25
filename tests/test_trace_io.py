"""trace.json 落盘与 TaskStore steps 字段。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from api.task_store import TaskStore
from observability.trace_io import read_trace, write_trace


class TraceIoTests(unittest.TestCase):
    def test_write_and_read_trace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            doc = {
                "thread_id": "t1",
                "status": "done",
                "steps": [{"seq": 1, "kind": "tool", "name": "x", "status": "ok"}],
                "failed_steps": [],
            }
            path = write_trace(tmp, doc)
            self.assertTrue(Path(path).is_file())
            loaded = read_trace(path)
            self.assertEqual(loaded["thread_id"], "t1")
            self.assertEqual(len(loaded["steps"]), 1)


class TaskStoreTraceFieldsTests(unittest.TestCase):
    def test_create_has_steps_and_trace_path(self) -> None:
        store = TaskStore()
        rec = store.create("tid", "q")
        self.assertEqual(rec["steps"], [])
        self.assertIsNone(rec["trace_path"])

    def test_mark_done_stores_steps(self) -> None:
        store = TaskStore()
        store.create("tid", "q")
        steps = [{"seq": 1, "kind": "tool", "name": "a", "status": "ok"}]
        rec = store.mark_done("tid", "ok", session_dir="/s", steps=steps, trace_path="/s/trace.json")
        assert rec is not None
        self.assertEqual(rec["steps"], steps)
        self.assertEqual(rec["trace_path"], "/s/trace.json")


if __name__ == "__main__":
    unittest.main()
