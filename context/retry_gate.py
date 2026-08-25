"""
同工具禁重试闸（R1b）。

retryable=false 的失败登记后，同工具再次调用可短路返回，避免 LLM 重复连库。
与 failure_steps 一样用 ContextVar，绑定当前任务协程。
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Dict, Optional

# tool_name -> 上次不可重试错误原文
_retry_block_ctx: ContextVar[Optional[Dict[str, str]]] = ContextVar("retry_block", default=None)


def init_retry_gate() -> Token:
    return _retry_block_ctx.set({})


def reset_retry_gate(token: Token) -> None:
    _retry_block_ctx.reset(token)


def clear_retry_gate() -> None:
    blocked = _retry_block_ctx.get()
    if blocked is not None:
        blocked.clear()


def record_non_retryable(tool: str, message: str) -> None:
    """format_tool_error(retryable=False) 时登记；未 init 则静默。"""
    blocked = _retry_block_ctx.get()
    if blocked is None:
        return
    blocked[tool] = message


def get_blocked_message(tool: str) -> Optional[str]:
    """若该工具已有不可重试失败，返回当时 message；否则 None。"""
    blocked = _retry_block_ctx.get()
    if not blocked:
        return None
    return blocked.get(tool)
