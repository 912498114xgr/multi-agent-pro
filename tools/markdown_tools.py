"""
tools/markdown_tools.py — Markdown 报告生成（报告撰写子 Agent 绑定）

写报告失败为 critical。
"""

from pathlib import Path
from typing import Annotated

from langchain_core.tools import tool

from context.session import get_session_context
from tools.hooks import hooks
from tools.tool_result import format_tool_error, format_tool_ok
from utils.path_utils import resolve_path


@tool
def generate_markdown(
    content: Annotated[str, "Markdown 文本内容"],
    filename: Annotated[str, "文件名（可含或不含 .md）"],
    path: Annotated[str, "相对保存路径，默认工作目录根"] = "",
) -> str:
    """
    生成 Markdown 报告文件。

    Args:
        content: 报告正文（Markdown 格式）
        filename: 如「效能周报_2026W12」，自动补 .md 后缀
        path: 子目录，如「reports」→ 保存到 session_dir/reports/xxx.md
    """
    hooks.report_tool("generate_markdown", {"filename": filename})

    if not filename.endswith(".md"):
        filename += ".md"

    session_dir = get_session_context()
    full_input = str(Path(path) / filename) if path and path != "." else filename
    file_path = Path(resolve_path(full_input, session_dir))
    file_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        file_path.write_text(content, encoding="utf-8")
        return format_tool_ok(
            tool="generate_markdown",
            body=f"Markdown文件 '{file_path}' 已成功生成并保存。",
        )
    except Exception as e:
        return format_tool_error(
            tool="generate_markdown",
            message=f"生成Markdown文件失败: {e}",
            error_type="io",
        )
