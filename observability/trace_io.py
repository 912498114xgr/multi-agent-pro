"""
Trace 文档读写（R2）。

用途：
    把 build_trace_document() 的结果持久化到会话目录，便于：
    1. 面试时打开 output/session_*/trace.json 讲完整调用链
    2. GET /api/tasks/{id}/trace 优先读文件（进程重启后只要文件还在仍可看 steps）

路径约定：{session_dir}/trace.json
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def write_trace(session_dir: str | Path, doc: Dict[str, Any]) -> str:
    """
    将 Trace 文档写入 session_dir/trace.json。

    Args:
        session_dir: 会话工作目录（通常 output/session_{thread_id}）
        doc: build_trace_document 产出的字典

    Returns:
        落盘文件的绝对路径（统一正斜杠，方便跨平台写进 task_store.trace_path）
    """
    root = Path(session_dir)
    root.mkdir(parents=True, exist_ok=True)
    path = root / "trace.json"
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path.resolve()).replace("\\", "/")


def read_trace(path: str | Path) -> Dict[str, Any]:
    """读取已落盘的 trace.json，供 API / 调试脚本使用。"""
    return json.loads(Path(path).read_text(encoding="utf-8"))
