"""
EfficiencyAgent 工具层单独测试入口。

用法（在项目根目录）:
  python tools/run_tests.py --list
  python tools/run_tests.py --test sql_validator
  python tools/run_tests.py --test db
  python tools/run_tests.py --test file
  python tools/run_tests.py --test markdown
  python tools/run_tests.py --test pdf
  python tools/run_tests.py --test tavily
  python tools/run_tests.py --test ragflow
  python tools/run_tests.py --test all
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 保证从任意目录运行都能找到项目包
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.test_helpers import setup_test_context, teardown_test_context, get_test_session_dir


def _header(name: str) -> None:
    print(f"\n{'='*60}\n  {name}\n{'='*60}")


def test_sql_validator() -> None:
    """纯逻辑测试：验证 SELECT 通过、DELETE/DROP/多语句被拒绝。"""
    _header("sql_validator 单元测试（无需数据库）")
    from tools.sql_validator import validate_readonly_sql, validate_table_name

    cases = [
        ("SELECT * FROM requirements LIMIT 10", True),
        ("DELETE FROM requirements", False),
        ("DROP TABLE requirements", False),
        ("SELECT 1; SELECT 2", False),
    ]
    for sql, expect_ok in cases:
        ok, err = validate_readonly_sql(sql)
        status = "PASS" if ok == expect_ok else "FAIL"
        print(f"  [{status}] {sql[:50]:50} -> ok={ok} {err}")

    ok, _ = validate_table_name("requirements")
    bad, _ = validate_table_name("req; DROP")
    print(f"  [{'PASS' if ok else 'FAIL'}] 合法表名 requirements")
    print(f"  [{'PASS' if not bad else 'FAIL'}] 非法表名 req; DROP")


def test_db() -> None:
    """集成测试：连真实 MySQL，查表、查 Sprint-12 开放缺陷、验证恶意 SQL 拦截。"""
    _header("db_tools（需 MySQL + xiaoneng_db 已导入假数据）")
    from tools.db_tools import list_sql_tables, get_table_data, execute_sql_query

    print(list_sql_tables.invoke({}))
    print("\n--- get_table_data: iterations ---")
    print(get_table_data.invoke({"table_name": "iterations"}))
    print("\n--- execute_sql_query: 当前迭代开放缺陷 ---")
    sql = """
    SELECT d.defect_code, d.title, d.severity, d.status
    FROM defects d
    JOIN iterations i ON d.iteration_id = i.iteration_id
    WHERE i.iteration_code = '2026-Sprint-12' AND d.status IN ('open','reopened')
    """
    print(execute_sql_query.invoke({"query": sql}))
    print("\n--- 恶意 SQL 应被拒绝 ---")
    print(execute_sql_query.invoke({"query": "DELETE FROM defects"}))


def test_file() -> None:
    """读取 test_data/session_test/Sprint12测试报告.md，需先 setup ContextVar。"""
    _header("read_file_content")
    tokens = setup_test_context()
    try:
        from tools.upload_file_read_tool import read_file_content
        result = read_file_content.invoke({"filename": "Sprint12测试报告.md"})
        print(result[:500] + ("..." if len(result) > 500 else ""))
    finally:
        teardown_test_context(tokens)


def test_markdown() -> None:
    """在 session_test/reports/ 下生成效能周报测试 md 文件。"""
    _header("generate_markdown")
    tokens = setup_test_context()
    try:
        from tools.markdown_tools import generate_markdown
        content = """# 研发效能周报（测试）

## Sprint-12 概况
- 计划故事点：30
- 已完成：12

## 开放缺陷
- BUG-2026-0121 中文乱码
- BUG-2026-0122 并发隔离
"""
        result = generate_markdown.invoke({
            "content": content,
            "filename": "效能周报_测试",
            "path": "reports",
        })
        print(result)
    finally:
        teardown_test_context(tokens)


def test_pdf() -> None:
    """先生成 md 再转 pdf，依赖 Windows + 已安装 Microsoft Word。"""
    _header("convert_md_to_pdf（需 Windows + Word）")
    tokens = setup_test_context()
    try:
        from tools.markdown_tools import generate_markdown
        from tools.pdf_tools import convert_md_to_pdf

        generate_markdown.invoke({
            "content": "# PDF测试\n\n这是一份测试报告。",
            "filename": "pdf_test.md",
        })
        result = convert_md_to_pdf.invoke({"md_filename": "pdf_test.md"})
        print(result)
    finally:
        teardown_test_context(tokens)


def test_tavily() -> None:
    """调用 Tavily 真实 API，需网络和 .env 中的 TAVILY_API_KEY。"""
    _header("internet_search（需网络 + TAVILY_API_KEY）")
    from tools.tavily_tool import internet_search
    result = internet_search.invoke({
        "query": "研发效能如何提效",
        "max_results": 5,
    })
    print(result[:800] + ("..." if len(result) > 800 else ""))


def test_ragflow() -> None:
    """未配置 RAGFlow 时应返回 stub 提示，不应崩溃。"""
    _header("ragflow_tools（未配置时返回 stub 提示）")
    from tools.ragflow_tools import get_assistant_list, create_ask_delete
    print(get_assistant_list.invoke({}))
    print(create_ask_delete.invoke({
        "chat_name": "研发规范助手",
        "question": "发布流程是什么？",
    }))


TESTS = {
    "sql_validator": test_sql_validator,
    "db": test_db,
    "file": test_file,
    "markdown": test_markdown,
    "pdf": test_pdf,
    "tavily": test_tavily,
    "ragflow": test_ragflow,
}


def test_all() -> None:
    for name, fn in TESTS.items():
        try:
            fn()
        except Exception as e:
            print(f"\n[ERROR] {name}: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(description="EfficiencyAgent 工具层测试")
    parser.add_argument("--list", action="store_true", help="列出可测项")
    parser.add_argument("--test", choices=list(TESTS.keys()) + ["all"], help="运行指定测试")
    args = parser.parse_args()

    if args.list:
        print("可测试项:")
        for k, fn in TESTS.items():
            print(f"  {k:15} {fn.__doc__ or fn.__name__}")
        print("  all             运行全部")
        return

    if not args.test:
        parser.print_help()
        return

    if args.test == "all":
        test_all()
    else:
        TESTS[args.test]()


if __name__ == "__main__":
    main()
