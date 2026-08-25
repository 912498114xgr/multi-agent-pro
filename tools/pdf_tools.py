"""
tools/pdf_tools.py — Markdown 转 PDF（报告撰写子 Agent 绑定）

PDF 为 optional：失败可降级，仍保留 Markdown。
"""

from pathlib import Path
from typing import Annotated, Optional

from langchain_core.tools import tool

from context.session import get_session_context
from tools.hooks import hooks
from tools.tool_result import format_tool_error, format_tool_ok
from utils.path_utils import resolve_path
from utils.word_converter import convert_md_to_pdf_via_word


@tool
def convert_md_to_pdf(
    md_filename: Annotated[str, "Markdown 文件路径"],
    pdf_filename: Annotated[Optional[str], "输出 PDF 路径（可选）"] = None,
) -> str:
    """
    将 Markdown 转为 PDF。

    Args:
        md_filename: 源 md 路径，相对 session 目录，如「reports/效能周报.md」
        pdf_filename: 可选；不传则与 md 同目录同名 .pdf
    """
    hooks.report_tool("convert_md_to_pdf", {"md_filename": md_filename})

    try:
        session_dir = get_session_context()
        md_abs = Path(resolve_path(str(Path(md_filename).with_suffix(".md")), session_dir))
        if not md_abs.exists():
            return format_tool_error(
                tool="convert_md_to_pdf",
                message=f"文件不存在 {md_abs}",
                error_type="not_found",
            )

        if pdf_filename:
            pdf_abs = Path(resolve_path(str(Path(pdf_filename).with_suffix(".pdf")), session_dir))
        else:
            pdf_abs = md_abs.with_suffix(".pdf")

        body = convert_md_to_pdf_via_word(md_abs, pdf_abs)
        # word_converter 失败时可能返回错误文案；简单探测
        if isinstance(body, str) and ("失败" in body or "错误" in body):
            return format_tool_error(
                tool="convert_md_to_pdf",
                message=body,
                error_type="upstream",
            )
        return format_tool_ok(tool="convert_md_to_pdf", body=str(body))
    except Exception as e:
        return format_tool_error(
            tool="convert_md_to_pdf",
            message=f"转换失败: {e}",
            error_type="upstream",
        )
