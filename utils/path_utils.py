"""
utils/path_utils.py — 统一文件路径解析

Agent 和 LLM 经常生成带「虚拟前缀」的路径，例如：
  /workspace/report.md
  /mnt/data/xxx.md
本函数负责清洗这些前缀，并把相对路径安全地拼接到 session_dir 内。

特殊规则：
  1. 路径含 updated/ → 解析到项目根下的上传目录（用户上传文件）
  2. 路径含重复的 session_xxx/session_xxx → 去嵌套，防止目录错乱
  3. Windows 下 /开头无盘符的路径 → 视为相对 session_dir 的子路径
"""

import os
from pathlib import Path
from typing import Optional


def resolve_path(filename: str, session_dir: Optional[str] = None) -> str:
    """
    将 LLM/用户传入的文件名或路径解析为绝对路径字符串。

    Args:
        filename: 文件名或路径（可能是虚拟路径、相对路径、绝对路径）
        session_dir: 当前会话工作目录（ContextVar 中的 session_dir）

    Returns:
        解析后的绝对路径字符串
    """
    path = Path(filename)
    path_str = filename.replace("\\", "/")

    # --- 步骤1：剥离 LLM 常见的虚拟路径前缀 ---
    virtual_prefixes = ["/workspace", "/mnt/data", "/home/user"]
    for prefix in virtual_prefixes:
        if path_str.startswith(prefix):
            cleaned = path_str[len(prefix):].lstrip("/")
            path = Path(cleaned)
            path_str = str(path).replace("\\", "/")
            break

    # --- 步骤2：上传目录特殊处理 ---
    # 用户上传文件存在 updated/session_xxx/ 下，工具读取时需走这条分支
    if "updated/" in path_str:
        idx = path_str.find("updated/")
        relative_part = path_str[idx:]
        return str(Path(relative_part).resolve())

    # 无 session 上下文时，直接解析为当前工作目录下的绝对路径
    if not session_dir:
        return str(path.resolve())

    session_path = Path(session_dir).resolve()
    session_name = session_path.name  # 如 session_abc-123
    is_unix_abs = path_str.startswith("/")

    # --- 步骤3：绝对路径处理 ---
    if path.is_absolute() or (os.name == "nt" and is_unix_abs):
        # Windows：/foo/bar 无盘符 → 拼到 session_dir 下
        if os.name == "nt" and is_unix_abs and not path.drive:
            full_path = session_path / path_str.lstrip("/")
        else:
            full_path = path.resolve()

        try:
            # 路径在 session 内时，检查是否有 session_name 重复嵌套
            if session_path in full_path.parents or full_path == session_path:
                parts = full_path.parts
                for i in range(len(parts) - 1):
                    if parts[i] == session_name and parts[i + 1] == session_name:
                        return str(session_path / full_path.name)
                return str(full_path)
        except Exception:
            pass
        return str(full_path)

    # --- 步骤4：相对路径处理 ---
    parts = path.parts
    # 路径已含 session 目录名时，只取文件名，避免 output/session_x/session_x/file
    if session_name in parts:
        return str(session_path / path.name)
    if parts and parts[0] == "output":
        return str(session_path / path.name)
    return str(session_path / path)
