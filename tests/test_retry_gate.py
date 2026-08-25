"""R1b: retryable=false 同工具短路。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from context.failure_steps import init_failure_steps, reset_failure_steps
from context.retry_gate import (
    get_blocked_message,
    init_retry_gate,
    record_non_retryable,
    reset_retry_gate,
)
from context.trace import get_trace_steps, init_trace, reset_trace
from tools.tool_result import begin_tool, format_tool_error, parse_tool_result


class RetryGateUnitTests(unittest.TestCase):
    def setUp(self) -> None:
        self._fail_tok = init_failure_steps()
        self._retry_tok = init_retry_gate()
        self._trace_tok = init_trace(thread_id="t-retry", query="q")

    def tearDown(self) -> None:
        reset_trace(self._trace_tok)
        reset_retry_gate(self._retry_tok)
        reset_failure_steps(self._fail_tok)

    def test_format_error_records_non_retryable(self) -> None:
        format_tool_error(
            tool="list_sql_tables",
            message="Can't connect",
            error_type="upstream",
            retryable=False,
        )
        self.assertEqual(get_blocked_message("list_sql_tables"), "Can't connect")

    def test_retryable_true_does_not_block(self) -> None:
        format_tool_error(
            tool="internet_search",
            message="429",
            error_type="upstream",
            retryable=True,
        )
        self.assertIsNone(get_blocked_message("internet_search"))

    def test_begin_tool_short_circuits(self) -> None:
        record_non_retryable("list_sql_tables", "db down")
        out = begin_tool("list_sql_tables")
        self.assertIsNotNone(out)
        parsed = parse_tool_result(out or "")
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertFalse(parsed["ok"])
        self.assertEqual(parsed["error_type"], "policy")
        self.assertIn("short_circuited_retry", parsed["message"])
        steps = get_trace_steps()
        tool_steps = [s for s in steps if s.get("kind") == "tool"]
        self.assertTrue(any("short_circuited_retry" in (s.get("message") or "") for s in tool_steps))

    def test_begin_tool_allows_first_call(self) -> None:
        self.assertIsNone(begin_tool("list_sql_tables"))


class DbToolShortCircuitTests(unittest.TestCase):
    def setUp(self) -> None:
        self._fail_tok = init_failure_steps()
        self._retry_tok = init_retry_gate()
        self._trace_tok = init_trace(thread_id="t-db", query="q")

    def tearDown(self) -> None:
        reset_trace(self._trace_tok)
        reset_retry_gate(self._retry_tok)
        reset_failure_steps(self._fail_tok)

    def test_list_sql_tables_does_not_connect_on_retry(self) -> None:
        from tools.db_tools import list_sql_tables

        format_tool_error(
            tool="list_sql_tables",
            message="Can't connect to MySQL",
            error_type="upstream",
            retryable=False,
        )
        with patch("tools.db_tools.connect") as mock_connect:
            out = list_sql_tables.invoke({})
            mock_connect.assert_not_called()
        parsed = parse_tool_result(out)
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertIn("short_circuited_retry", parsed["message"])


if __name__ == "__main__":
    unittest.main()
