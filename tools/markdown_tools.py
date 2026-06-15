"""
tools/markdown_tools.py — Markdown 报告生成（报告撰写子 Agent 绑定）

将 LLM 生成的报告正文写入 .md 文件，保存在当前会话的 output/session_xxx/ 目录下。
路径由 ContextVar + path_utils 解析，确保不会写到其他用户目录。
"""

from pathlib import Path
from typing import Annotated

from langchain_core.tools import tool

from context.session import get_session_context
from tools.hooks import hooks
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
    # path 为空时直接存 session 根目录；否则拼 path/filename
    full_input = str(Path(path) / filename) if path and path != "." else filename
    file_path = Path(resolve_path(full_input, session_dir))
    file_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        file_path.write_text(content, encoding="utf-8")
        return f"Markdown文件 '{file_path}' 已成功生成并保存。"
    except Exception as e:
        return f"生成Markdown文件失败: {str(e)}"
