"""
tools/upload_file_read_tool.py — 文件读取工具（主 Agent 直接绑定）

读取当前会话工作目录中的用户上传文件或已生成报告。
依赖 context.session.get_session_context() 获取工作目录，无需 LLM 传绝对路径。

支持格式：.md .txt .docx .pdf .xlsx .xls
重依赖（pandas/docx/pypdf）采用函数内懒加载，避免 import 时内存开销。
"""

from pathlib import Path
from typing import Annotated

from langchain_core.tools import tool

from context.session import get_session_context
from utils.path_utils import resolve_path

# 白名单扩展名，不在列表内直接拒绝，防止读取二进制或可执行文件
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
    # 进度由 runner 在主图 model 节点上报；此处不再走 hooks，避免重复 WebSocket 事件。
    session_dir = get_session_context()
    file_path = Path(resolve_path(filename, session_dir))

    if not file_path.exists():
        return f"错误：文件 '{filename}' 不存在 (解析路径: {file_path})"

    ext = file_path.suffix.lower()
    if ext not in ALLOWED_EXT:
        return f"错误：不支持的文件格式 '{ext}'，允许: {', '.join(sorted(ALLOWED_EXT))}"

    try:
        if ext in (".md", ".txt"):
            return file_path.read_text(encoding="utf-8")

        if ext == ".docx":
            try:
                import docx
            except ImportError:
                return "错误：未安装 python-docx"
            doc = docx.Document(str(file_path))
            return "\n".join(p.text for p in doc.paragraphs)

        if ext == ".pdf":
            try:
                import pypdf
            except ImportError:
                return "错误：未安装 pypdf"
            reader = pypdf.PdfReader(str(file_path))
            return "\n".join(page.extract_text() or "" for page in reader.pages)

        if ext in (".xlsx", ".xls"):
            try:
                import pandas as pd
            except ImportError:
                return "错误：未安装 pandas"
            df = pd.read_excel(str(file_path))
            # Excel 返回摘要 + 前5行 + 统计，避免把大表全塞给 LLM
            return "\n".join([
                f"文件: {filename}",
                f"行数: {len(df)}, 列数: {len(df.columns)}",
                f"列名: {', '.join(df.columns.astype(str))}",
                "\n[前5行]:", df.head().to_string(index=False),
                "\n[统计]:", df.describe().to_string(),
            ])

        return file_path.read_text(encoding="utf-8")
    except Exception as e:
        return f"读取文件出错: {str(e)}"
