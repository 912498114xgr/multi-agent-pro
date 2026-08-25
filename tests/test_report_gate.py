"""R1b: critical 失败后禁止 generate_markdown 写充实报告。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from context.failure_steps import init_failure_steps, record_failure_step, reset_failure_steps
from context.retry_gate import init_retry_gate, reset_retry_gate
from context.trace import init_trace, reset_trace
from tools.markdown_tools import generate_markdown
from tools.tool_result import parse_tool_result


class ReportGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self._fail_tok = init_failure_steps()
        self._retry_tok = init_retry_gate()
        self._trace_tok = init_trace(thread_id="t-gate", query="q")

    def tearDown(self) -> None:
        reset_trace(self._trace_tok)
        reset_retry_gate(self._retry_tok)
        reset_failure_steps(self._fail_tok)

    def test_blocks_and_does_not_write_file(self) -> None:
        record_failure_step(
            {
                "tool": "list_sql_tables",
                "role": "critical",
                "message": "db down",
                "error_type": "upstream",
            }
        )
        with tempfile.TemporaryDirectory() as tmp:
            with patch("tools.markdown_tools.get_session_context", return_value=tmp):
                out = generate_markdown.invoke(
                    {"content": "# 假充实报告\n捏造指标 999", "filename": "blocked.md"}
                )
            parsed = parse_tool_result(out)
            self.assertIsNotNone(parsed)
            assert parsed is not None
            self.assertFalse(parsed["ok"])
            self.assertEqual(parsed["error_type"], "policy")
            self.assertIn("成稿门禁", parsed["message"])
            self.assertFalse((Path(tmp) / "blocked.md").exists())

    def test_allows_when_only_optional_failure(self) -> None:
        record_failure_step(
            {
                "tool": "internet_search",
                "role": "optional",
                "message": "search down",
                "error_type": "upstream",
            }
        )
        with tempfile.TemporaryDirectory() as tmp:
            with patch("tools.markdown_tools.get_session_context", return_value=tmp):
                out = generate_markdown.invoke(
                    {"content": "# ok", "filename": "ok.md"}
                )
            parsed = parse_tool_result(out)
            self.assertIsNotNone(parsed)
            assert parsed is not None
            self.assertTrue(parsed["ok"])
            self.assertTrue((Path(tmp) / "ok.md").exists())


if __name__ == "__main__":
    unittest.main()
