"""
协程级失败步骤收集（R1）。

子 Agent 内部的工具失败不会出现在主 Agent astream 的 tools 节点里，
因此在 format_tool_error 时写入 ContextVar，供 runner 结束时决策。
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Any, Dict, List, Optional

_failure_steps_ctx: ContextVar[Optional[List[Dict[str, Any]]]] = ContextVar(
    "failure_steps",
    default=None,
)


def init_failure_steps() -> Token:
    """任务开始时调用，返回 token 供 finally 重置。"""
    return _failure_steps_ctx.set([])


def reset_failure_steps(token: Token) -> None:
    _failure_steps_ctx.reset(token)


def clear_failure_steps() -> None:
    """无 token 时清空（测试辅助）。"""
    steps = _failure_steps_ctx.get()
    if steps is not None:
        steps.clear()


def get_failure_steps() -> List[Dict[str, Any]]:
    steps = _failure_steps_ctx.get()
    if steps is None:
        return []
    return list(steps)


def record_failure_step(step: Dict[str, Any]) -> None:
    """若未 init（例如单测直接调工具），静默跳过，避免污染全局。"""
    steps = _failure_steps_ctx.get()
    if steps is None:
        return
    steps.append(dict(step))
