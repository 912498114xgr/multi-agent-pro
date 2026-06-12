"""
协程级上下文（ContextVar）。

在 FastAPI 异步场景下，多个用户请求运行在同一线程的不同协程中。
ContextVar 保证每个请求的 session_dir、thread_id、trace_id 相互隔离，避免串台。
"""

import uuid
from contextvars import ContextVar
from typing import Optional, Tuple

_session_dir_ctx: ContextVar[Optional[str]] = ContextVar("session_dir", default=None)
_thread_id_ctx: ContextVar[Optional[str]] = ContextVar("thread_id", default=None)
_trace_id_ctx: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)
_user_id_ctx: ContextVar[Optional[str]] = ContextVar("user_id", default=None)


def set_session_context(path: str):
    """设置当前会话工作目录（绝对路径字符串）。"""
    return _session_dir_ctx.set(path)


def get_session_context() -> Optional[str]:
    return _session_dir_ctx.get()


def set_thread_context(thread_id: str):
    """设置当前任务 thread_id，用于 WebSocket 定向推送。"""
    return _thread_id_ctx.set(thread_id)


def get_thread_context() -> Optional[str]:
    return _thread_id_ctx.get()


def set_trace_context(trace_id: Optional[str] = None):
    """设置链路追踪 ID，默认自动生成 UUID。"""
    return _trace_id_ctx.set(trace_id or str(uuid.uuid4()))


def get_trace_id() -> Optional[str]:
    return _trace_id_ctx.get()


def set_user_context(user_id: str):
    return _user_id_ctx.set(user_id)


def get_user_id() -> Optional[str]:
    return _user_id_ctx.get()


def reset_session_context(
    session_token,
    thread_token=None,
    trace_token=None,
    user_token=None,
):
    _session_dir_ctx.reset(session_token)
    if thread_token:
        _thread_id_ctx.reset(thread_token)
    if trace_token:
        _trace_id_ctx.reset(trace_token)
    if user_token:
        _user_id_ctx.reset(user_token)


def setup_request_context(
    session_dir: str,
    thread_id: str,
    user_id: str = "anonymous",
    trace_id: Optional[str] = None,
) -> Tuple:
    """一次性设置请求上下文，返回 token 元组供 finally 中 reset。"""
    session_token = set_session_context(session_dir)
    thread_token = set_thread_context(thread_id)
    trace_token = set_trace_context(trace_id)
    user_token = set_user_context(user_id)
    return session_token, thread_token, trace_token, user_token


def reset_all_tokens(tokens: Tuple) -> None:
    session_token, thread_token, trace_token, user_token = tokens
    reset_session_context(session_token, thread_token, trace_token, user_token)
