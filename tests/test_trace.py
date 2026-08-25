"""R2 Trace collector: start/end timing and events."""

from __future__ import annotations

import time
import unittest

from context.failure_steps import get_failure_steps, init_failure_steps, reset_failure_steps
from context.trace import (
    build_trace_document,
    get_trace_steps,
    init_trace,
    reset_trace,
    trace_event,
    trace_tool_end,
    trace_tool_start,
)


class TraceCollectorTests(unittest.TestCase):
    def test_tool_start_end_records_duration_and_ok(self) -> None:
        token = init_trace()
        try:
            trace_tool_start("list_sql_tables")
            time.sleep(0.02)
            trace_tool_end(
                tool="list_sql_tables",
                ok=True,
                role="critical",
            )
            steps = get_trace_steps()
            self.assertEqual(len(steps), 1)
            step = steps[0]
            self.assertEqual(step["kind"], "tool")
            self.assertEqual(step["name"], "list_sql_tables")
            self.assertEqual(step["status"], "ok")
            self.assertEqual(step["role"], "critical")
            self.assertGreaterEqual(step["duration_ms"], 15)
            self.assertEqual(step["seq"], 1)
        finally:
            reset_trace(token)

    def test_tool_end_failure_also_records_failure_steps(self) -> None:
        t_token = init_trace()
        f_token = init_failure_steps()
        try:
            trace_tool_start("internet_search")
            trace_tool_end(
                tool="internet_search",
                ok=False,
                role="optional",
                message="down",
                error_type="upstream",
                record_failure=True,
            )
            steps = get_trace_steps()
            self.assertEqual(steps[0]["status"], "error")
            self.assertEqual(steps[0]["error_type"], "upstream")
            fails = get_failure_steps()
            self.assertEqual(len(fails), 1)
            self.assertEqual(fails[0]["tool"], "internet_search")
        finally:
            reset_failure_steps(f_token)
            reset_trace(t_token)

    def test_uninitialized_trace_is_noop(self) -> None:
        # Should not raise
        trace_tool_start("x")
        trace_tool_end(tool="x", ok=True, role="optional")
        trace_event(kind="assistant", name="数据查询助手", status="ok")
        self.assertEqual(get_trace_steps(), [])

    def test_trace_event_and_document(self) -> None:
        token = init_trace(thread_id="t1", query="q")
        try:
            trace_event(kind="assistant", name="数据查询助手", status="ok")
            trace_tool_start("execute_sql_query")
            trace_tool_end(tool="execute_sql_query", ok=True, role="critical")
            doc = build_trace_document(
                status="done",
                failed_steps=[],
                session_dir="/tmp/s",
            )
            self.assertEqual(doc["thread_id"], "t1")
            self.assertEqual(doc["query"], "q")
            self.assertEqual(doc["status"], "done")
            self.assertEqual(len(doc["steps"]), 2)
            self.assertIn("started_at", doc)
            self.assertIn("finished_at", doc)
            self.assertIn("duration_ms", doc)
        finally:
            reset_trace(token)


if __name__ == "__main__":
    unittest.main()
