"""Monitor 失败汇总事件文案。"""

from __future__ import annotations

import unittest

from api.monitor import ToolMonitor


class FailuresSummaryTests(unittest.TestCase):
    def test_report_failures_summary_emits_once_with_counts(self) -> None:
        mon = ToolMonitor()
        emitted = []

        def capture(event_type, message, data=None):
            emitted.append((event_type, message, data or {}))

        mon._emit = capture  # type: ignore[method-assign]
        steps = [
            {"tool": "list_sql_tables", "role": "critical", "message": "a"},
            {"tool": "list_sql_tables", "role": "critical", "message": "b"},
            {"tool": "internet_search", "role": "optional", "message": "c"},
        ]
        mon.report_failures_summary(steps)
        self.assertEqual(len(emitted), 1)
        event, message, data = emitted[0]
        self.assertEqual(event, "failures_summary")
        self.assertIn("关键 2", message)
        self.assertIn("可选 1", message)
        self.assertIn("list_sql_tables×2", message)
        self.assertEqual(data["critical_count"], 2)
        self.assertEqual(data["optional_count"], 1)

    def test_report_task_result_message_not_claim_finished(self) -> None:
        mon = ToolMonitor()
        emitted = []
        mon._emit = lambda e, m, d=None: emitted.append((e, m))  # type: ignore[method-assign]
        mon.report_task_result("hello")
        self.assertEqual(emitted[0][0], "task_result")
        self.assertNotIn("任务执行完成", emitted[0][1])
        self.assertIn("终态", emitted[0][1])


if __name__ == "__main__":
    unittest.main()
