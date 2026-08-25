"""
tools/upload_file_read_tool.py — 文件读取工具（主 Agent 直接绑定）

读文件失败视为 critical（上传复盘场景依赖材料）。
"""

from pathlib import Path
from typing import Annotated

from langchain_core.tools import tool

from context.session import get_session_context
from tools.tool_result import begin_tool, format_tool_error, format_tool_ok
from utils.path_utils import resolve_path

ALLOWED_EXT = {".md", ".txt", ".docx", ".pdf", ".xlsx", ".xls"}


@tool
def read_file_content(
    filename: Annotated[str, "文件名或路径（.md .txt .docx .pdf .xlsx .xls）"],
    instruction: Annotated[str, "提取指令"] = "提取全部内容",
) -> str:
    """
    读取工作目录中的文件内容。

    Args:
        filename: 只需传文件名如「Sprint12测试报告.md」，不要带目录前缀
        instruction: 预留参数，后续可做定向摘要（当前读取全文）
    """
    blocked = begin_tool("read_file_content", {"filename": filename, "instruction": instruction})
    if blocked:
        return blocked

    session_dir = get_session_context()
    file_path = Path(resolve_path(filename, session_dir))

    if not file_path.exists():
        return format_tool_error(
            tool="read_file_content",
            message=f"文件 '{filename}' 不存在 (解析路径: {file_path})",
            error_type="not_found",
        )

    ext = file_path.suffix.lower()
    if ext not in ALLOWED_EXT:
        return format_tool_error(
            tool="read_file_content",
            message=f"不支持的文件格式 '{ext}'，允许: {', '.join(sorted(ALLOWED_EXT))}",
            error_type="validation",
        )

    try:
        if ext in (".md", ".txt"):
            return format_tool_ok(tool="read_file_content", body=file_path.read_text(encoding="utf-8"))

        if ext == ".docx":
            try:
                import docx
            except ImportError:
                return format_tool_error(
                    tool="read_file_content",
                    message="未安装 python-docx",
                    error_type="dependency",
                )
            doc = docx.Document(str(file_path))
            return format_tool_ok(
                tool="read_file_content",
                body="\n".join(p.text for p in doc.paragraphs),
            )

        if ext == ".pdf":
            try:
                import pypdf
            except ImportError:
                return format_tool_error(
                    tool="read_file_content",
                    message="未安装 pypdf",
                    error_type="dependency",
                )
            reader = pypdf.PdfReader(str(file_path))
            return format_tool_ok(
                tool="read_file_content",
                body="\n".join(page.extract_text() or "" for page in reader.pages),
            )

        if ext in (".xlsx", ".xls"):
            try:
                import pandas as pd
            except ImportError:
                return format_tool_error(
                    tool="read_file_content",
                    message="未安装 pandas",
                    error_type="dependency",
                )
            df = pd.read_excel(str(file_path))
            body = "\n".join([
                f"文件: {filename}",
                f"行数: {len(df)}, 列数: {len(df.columns)}",
                f"列名: {', '.join(df.columns.astype(str))}",
                "\n[前5行]:", df.head().to_string(index=False),
                "\n[统计]:", df.describe().to_string(),
            ])
            return format_tool_ok(tool="read_file_content", body=body)

        return format_tool_ok(tool="read_file_content", body=file_path.read_text(encoding="utf-8"))
    except Exception as e:
        return format_tool_error(
            tool="read_file_content",
            message=f"读取文件出错: {e}",
            error_type="upstream",
        )
