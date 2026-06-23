"""
context/session.py — 协程级请求上下文（ContextVar）

为什么需要 ContextVar？
  FastAPI 异步模式下，多个用户请求在同一线程的不同协程中并发执行。
  全局变量会被所有协程共享导致「串台」；threading.local 对 asyncio 无效。
  ContextVar 是 Python 3.7+ 为异步设计的「协程级局部变量」。

本模块存储的上下文：
  session_dir — 当前任务的工作目录（工具写文件、读文件时用）
  thread_id   — 任务 ID（WebSocket 定向推送、checkpoint 用）
  trace_id    — 链路追踪 ID（日志关联用）
  user_id     — 调用方用户（鉴权后写入，MVP 默认 anonymous）

典型用法（在 run_deep_agent 中）：
  tokens = setup_request_context(session_dir, thread_id)
  try:
      ... 执行业务 ...
  finally:
      reset_all_tokens(tokens)   # 必须清理，防止污染下一个协程
"""

import uuid
from contextvars import ContextVar
from typing import Optional, Tuple

# 四个独立的 ContextVar，default=None 表示未设置时 get() 返回 None
_session_dir_ctx: ContextVar[Optional[str]] = ContextVar("session_dir", default=None)
_thread_id_ctx: ContextVar[Optional[str]] = ContextVar("thread_id", default=None)
_trace_id_ctx: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)
_user_id_ctx: ContextVar[Optional[str]] = ContextVar("user_id", default=None)
_active_assistant_ctx: ContextVar[Optional[str]] = ContextVar("active_assistant", default=None)


def set_session_context(path: str):
    """
    设置当前协程的会话工作目录（绝对路径字符串）。
    返回 token，供 reset 时恢复上一状态。
    """
    return _session_dir_ctx.set(path)


def get_session_context() -> Optional[str]:
    """工具层（read_file、generate_markdown）通过此函数获取工作目录。"""
    return _session_dir_ctx.get()


def set_thread_context(thread_id: str):
    """绑定 thread_id，monitor 推送 WS 消息时用来找到对应连接。"""
    return _thread_id_ctx.set(thread_id)


def get_thread_context() -> Optional[str]:
    return _thread_id_ctx.get()


def set_trace_context(trace_id: Optional[str] = None):
    """设置 trace_id；未传入时自动生成 UUID。"""
    return _trace_id_ctx.set(trace_id or str(uuid.uuid4()))


def get_trace_id() -> Optional[str]:
    return _trace_id_ctx.get()


def set_user_context(user_id: str):
    return _user_id_ctx.set(user_id)


def get_user_id() -> Optional[str]:
    return _user_id_ctx.get()


def set_active_assistant(name: str):
    """主 Agent 委派子 Agent 时记录名称，供 assistant_done 使用。"""
    return _active_assistant_ctx.set(name)


def get_active_assistant() -> Optional[str]:
    return _active_assistant_ctx.get()


def reset_active_assistant(token) -> None:
    if token is not None:
        _active_assistant_ctx.reset(token)


def clear_active_assistant() -> None:
    _active_assistant_ctx.set(None)


def reset_session_context(
    session_token,
    thread_token=None,
    trace_token=None,
    user_token=None,
):
    """
    按 token 恢复 ContextVar 到 set 之前的状态。
    token 是 set() 的返回值，每个协程独立，不可跨协程复用。
    """
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
    """
    一次性设置本请求所需的全部上下文。
    返回 (session_token, thread_token, trace_token, user_token) 四元组。
    """
    session_token = set_session_context(session_dir)
    thread_token = set_thread_context(thread_id)
    trace_token = set_trace_context(trace_id)
    user_token = set_user_context(user_id)
    return session_token, thread_token, trace_token, user_token


def reset_all_tokens(tokens: Tuple) -> None:
    """setup_request_context 的配对清理函数，放在 finally 块中。"""
    session_token, thread_token, trace_token, user_token = tokens
    reset_session_context(session_token, thread_token, trace_token, user_token)
