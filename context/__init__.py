"""
context 包 — 协程级请求上下文（ContextVar）。

详见 context/session.py。
工具层通过 get_session_context() 获取工作目录；
API 层在 run_deep_agent 入口 setup，finally 中 reset。
"""

from context.session import (
    get_session_context,
    get_thread_context,
    get_trace_id,
    get_user_id,
    reset_all_tokens,
    reset_session_context,
    set_session_context,
    set_thread_context,
    set_trace_context,
    set_user_context,
    setup_request_context,
)

__all__ = [
    "set_session_context",
    "get_session_context",
    "set_thread_context",
    "get_thread_context",
    "set_trace_context",
    "get_trace_id",
    "set_user_context",
    "get_user_id",
    "reset_session_context",
    "reset_all_tokens",
    "setup_request_context",
]
