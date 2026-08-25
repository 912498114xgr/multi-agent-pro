"""R1: structured tool results and critical/optional status decision."""

from __future__ import annotations

import unittest

from context.failure_steps import (
    clear_failure_steps,
    get_failure_steps,
    init_failure_steps,
    reset_failure_steps,
)
from tools.tool_result import (
    TOOL_RESULT_MARKER,
    decide_task_status,
    format_tool_error,
    format_tool_ok,
    parse_tool_result,
    role_for_tool,
)


class ToolResultFormatTests(unittest.TestCase):
    def test_format_error_contains_marker_and_parseable_payload(self) -> None:
        text = format_tool_error(
            tool="internet_search",
            message="TAVILY_API_KEY 未配置",
            error_type="config_missing",
            retryable=False,
        )
        self.assertIn(TOOL_RESULT_MARKER, text)
        parsed = parse_tool_result(text)
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertFalse(parsed["ok"])
        self.assertEqual(parsed["tool"], "internet_search")
        self.assertEqual(parsed["role"], "optional")
        self.assertEqual(parsed["error_type"], "config_missing")
        self.assertIn("TAVILY_API_KEY", parsed["message"])

    def test_format_ok_keeps_body_for_llm(self) -> None:
        text = format_tool_ok(tool="list_sql_tables", body="可用的表有：defects")
        self.assertIn("可用的表有：defects", text)
        parsed = parse_tool_result(text)
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertTrue(parsed["ok"])
        self.assertEqual(parsed["role"], "critical")

    def test_role_for_known_tools(self) -> None:
        self.assertEqual(role_for_tool("execute_sql_query"), "critical")
        self.assertEqual(role_for_tool("internet_search"), "optional")
        self.assertEqual(role_for_tool("convert_md_to_pdf"), "optional")


class FailureCollectorTests(unittest.TestCase):
    def test_format_error_records_into_context(self) -> None:
        token = init_failure_steps()
        try:
            format_tool_error(
                tool="internet_search",
                message="网络搜索失败",
                error_type="upstream",
            )
            steps = get_failure_steps()
            self.assertEqual(len(steps), 1)
            self.assertEqual(steps[0]["tool"], "internet_search")
            self.assertEqual(steps[0]["role"], "optional")
        finally:
            reset_failure_steps(token)

    def test_format_ok_does_not_record_failure(self) -> None:
        token = init_failure_steps()
        try:
            format_tool_ok(tool="list_sql_tables", body="ok")
            self.assertEqual(get_failure_steps(), [])
        finally:
            reset_failure_steps(token)


class DecideStatusTests(unittest.TestCase):
    def test_critical_failure_yields_error(self) -> None:
        status = decide_task_status(
            [
                {
                    "tool": "execute_sql_query",
                    "role": "critical",
                    "message": "db down",
                    "error_type": "upstream",
                }
            ]
        )
        self.assertEqual(status, "error")

    def test_only_optional_failure_yields_partial_success(self) -> None:
        status = decide_task_status(
            [
                {
                    "tool": "internet_search",
                    "role": "optional",
                    "message": "search down",
                    "error_type": "upstream",
                }
            ]
        )
        self.assertEqual(status, "partial_success")

    def test_no_failures_yields_done(self) -> None:
        self.assertEqual(decide_task_status([]), "done")

    def test_mixed_critical_wins(self) -> None:
        status = decide_task_status(
            [
                {"tool": "internet_search", "role": "optional", "message": "x", "error_type": "e"},
                {"tool": "list_sql_tables", "role": "critical", "message": "y", "error_type": "e"},
            ]
        )
        self.assertEqual(status, "error")


if __name__ == "__main__":
    unittest.main()
