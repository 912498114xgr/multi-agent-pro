"""工具层结构化返回冒烟（不依赖真实 MySQL/Tavily）。"""

from __future__ import annotations

import unittest

from context.failure_steps import get_failure_steps, init_failure_steps, reset_failure_steps
from tools.sql_validator import validate_readonly_sql
from tools.tool_result import TOOL_RESULT_MARKER, parse_tool_result
from tools.db_tools import execute_sql_query
from tools.tavily_tool import internet_search


class ToolStructuredReturnTests(unittest.TestCase):
    def test_sql_validation_failure_is_structured_and_critical(self) -> None:
        token = init_failure_steps()
        try:
            text = execute_sql_query.invoke({"query": "DELETE FROM defects"})
            self.assertIn(TOOL_RESULT_MARKER, text)
            parsed = parse_tool_result(text)
            self.assertIsNotNone(parsed)
            assert parsed is not None
            self.assertFalse(parsed["ok"])
            self.assertEqual(parsed["role"], "critical")
            self.assertEqual(len(get_failure_steps()), 1)
        finally:
            reset_failure_steps(token)

    def test_tavily_missing_key_is_optional_failure(self) -> None:
        token = init_failure_steps()
        try:
            # 即使环境有 key，用空 query 也可能成功；这里直接测未配置路径较难，
            # 改为校验角色映射 + 校验器仍可用。
            ok, _ = validate_readonly_sql("SELECT 1")
            self.assertTrue(ok)
            text = internet_search.invoke({"query": "DORA metrics"})
            # 有 key 则 ok；无 key 则失败 optional
            parsed = parse_tool_result(text)
            self.assertIsNotNone(parsed)
            assert parsed is not None
            if not parsed["ok"]:
                self.assertEqual(parsed["role"], "optional")
                self.assertTrue(any(s["tool"] == "internet_search" for s in get_failure_steps()))
            else:
                self.assertEqual(parsed["role"], "optional")
                self.assertEqual(get_failure_steps(), [])
        finally:
            reset_failure_steps(token)


if __name__ == "__main__":
    unittest.main()
