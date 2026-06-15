"""
utils/word_converter.py — Markdown 转 PDF（Windows Word COM）

流程：MD → HTML（markdown 库）→ 临时 .html → Word 打开 → 另存为 PDF
依赖：pywin32（Word COM）、markdown
仅适用于 Windows 且已安装 Microsoft Word 的环境。
"""

import logging
from pathlib import Path

try:
    import markdown
    import win32com.client
    import pythoncom
except ImportError:
    markdown = None
    win32com = None
    pythoncom = None


def convert_md_to_pdf_via_word(md_abs_path: Path, pdf_abs_path: Path) -> str:
    """
    将 Markdown 文件转为 PDF。

    Args:
        md_abs_path: 源 .md 文件绝对路径
        pdf_abs_path: 目标 .pdf 文件绝对路径

    Returns:
        成功或失败的中文描述字符串（给 LLM / 用户看，不抛异常）
    """
    if markdown is None or win32com is None:
        return "缺少依赖库，请安装: pip install pywin32 markdown"

    temp_html_path = md_abs_path.with_suffix(".temp.html")
    word_app = None

    try:
        # 1. Markdown → HTML
        md_content = md_abs_path.read_text(encoding="utf-8")
        html_body = markdown.markdown(md_content, extensions=["tables", "fenced_code"])
        html_content = f"""<html><head><meta charset="UTF-8">
        <style>body{{font-family:"Microsoft YaHei",sans-serif;}}
        table{{border-collapse:collapse;width:100%;}}
        th,td{{border:1px solid black;padding:8px;}}</style></head>
        <body>{html_body}</body></html>"""
        temp_html_path.write_text(html_content, encoding="utf-8")

        # 2. 启动 Word COM（单线程需 CoInitialize）
        pythoncom.CoInitialize()
        word_app = win32com.client.Dispatch("Word.Application")
        word_app.Visible = False
        word_app.DisplayAlerts = False

        doc = word_app.Documents.Open(str(temp_html_path.resolve()))
        pdf_abs_path.parent.mkdir(parents=True, exist_ok=True)
        doc.SaveAs(str(pdf_abs_path.resolve()), FileFormat=17)  # 17 = wdFormatPDF
        doc.Close(SaveChanges=0)

        if pdf_abs_path.exists():
            return f"成功转换: {pdf_abs_path} (Word引擎)"
        return f"转换完成但未生成文件: {pdf_abs_path}"
    except Exception as e:
        logging.error("Word转换PDF失败: %s", e, exc_info=True)
        return f"转换失败: {str(e)}"
    finally:
        # 3. 释放 Word 进程和临时 HTML，避免资源泄漏
        if word_app:
            try:
                word_app.Quit()
            except Exception:
                pass
        if temp_html_path.exists():
            try:
                temp_html_path.unlink()
            except Exception:
                pass
        if pythoncom:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass
