"""
tools/pdf_tools.py — Markdown 转 PDF（报告撰写子 Agent 绑定）

将已生成的 .md 报告转为 PDF，底层调用 utils.word_converter（Windows Word COM）。
需先由 generate_markdown 生成源文件，再调用本工具。
"""

from pathlib import Path
from typing import Annotated, Optional

from langchain_core.tools import tool

from context.session import get_session_context
from tools.hooks import hooks
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
            return f"错误：文件不存在 {md_abs}"

        if pdf_filename:
            pdf_abs = Path(resolve_path(str(Path(pdf_filename).with_suffix(".pdf")), session_dir))
        else:
            pdf_abs = md_abs.with_suffix(".pdf")

        return convert_md_to_pdf_via_word(md_abs, pdf_abs)
    except Exception as e:
        return f"转换失败: {str(e)}"
