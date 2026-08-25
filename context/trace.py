"""
协程级步骤 Trace 收集器（R2：步骤级状态与可展示 Trace）。

================================================================================
用途（面试/联调一句话）
================================================================================
在一次 Agent 任务执行期间，按时间顺序记录「谁调用了谁、成败、耗时」，
任务结束写成 output/session_{id}/trace.json，并通过 API/前端 Trace 面板展示。
解决：WebSocket 只有进度播报、嵌套子 Agent 工具结果进不了主图 astream 的问题。

================================================================================
为何用 ContextVar（而不是全局 list）
================================================================================
FastAPI 下多个任务协程并发；全局 list 会串台。
ContextVar 与 session/failure_steps 一样，绑定当前协程，finally 里 reset。

================================================================================
与 R1 failure_steps 的关系
================================================================================
- Trace：完整时间线（成功 + 失败工具、assistant、model_result、status）
- failure_steps：仅失败，供 decide_task_status → done / partial_success / error
工具失败时：trace_tool_end(..., record_failure=True) 会同时写入 failure_steps。

================================================================================
典型调用链
================================================================================
1. runner.run_deep_agent
     init_trace(thread_id, query)
     trace_event(kind=session / assistant / model_result / status)
2. 任意 @tool 入口 hooks.report_tool → trace_tool_start(name)   # 记开始时钟
3. format_tool_ok / format_tool_error → trace_tool_end(...)    # 算 duration_ms
4. runner 终态：build_trace_document → write_trace → task_store.steps/trace_path
5. finally：reset_trace(token)

================================================================================
单条 step 字段约定
================================================================================
seq, kind(session|assistant|tool|model_result|status), name, status(ok|error),
role(critical|optional, 仅 tool), duration_ms, message, error_type, ts, ...
"""

from __future__ import annotations

import datetime
import time
from contextvars import ContextVar, Token
from typing import Any, Dict, List, Optional

# 已完成的步骤列表（按 seq 递增）
_trace_steps_ctx: ContextVar[Optional[List[Dict[str, Any]]]] = ContextVar("trace_steps", default=None)
# 尚未 end 的工具开始时间：tool 名 → perf_counter；以及 _last::{name} → 实际 key（支持同名重入）
_trace_pending_ctx: ContextVar[Optional[Dict[str, Any]]] = ContextVar("trace_pending", default=None)
# 任务级元数据：thread_id / query / started_at / started_perf
_trace_meta_ctx: ContextVar[Optional[Dict[str, Any]]] = ContextVar("trace_meta", default=None)


def _now_iso() -> str:
    """UTC ISO8601 时间戳，写入每条 step.ts 与文档 started_at/finished_at。"""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def init_trace(*, thread_id: str = "", query: str = "") -> Token:
    """
    任务开始时初始化本协程的 Trace 上下文。

    Returns:
        Token：交给 finally 中 reset_trace，恢复 ContextVar，避免污染后续请求。

    副作用：
        - 清空 steps 列表
        - 清空 pending 开始时钟
        - 记录 thread_id、query、任务开始墙钟与 perf 时钟
    """
    _trace_pending_ctx.set({})
    _trace_meta_ctx.set(
        {
            "thread_id": thread_id,
            "query": query,
            "started_at": _now_iso(),
            "started_perf": time.perf_counter(),
        }
    )
    return _trace_steps_ctx.set([])


def reset_trace(token: Token) -> None:
    """与 init_trace 配对：恢复 steps，并清空 pending/meta，防止协程间泄漏。"""
    _trace_steps_ctx.reset(token)
    _trace_pending_ctx.set(None)
    _trace_meta_ctx.set(None)


def get_trace_steps() -> List[Dict[str, Any]]:
    """返回当前协程已记录步骤的副本；未 init 时返回空列表（安全 no-op）。"""
    steps = _trace_steps_ctx.get()
    if steps is None:
        return []
    return list(steps)


def _append_step(step: Dict[str, Any]) -> None:
    """内部：追加一步并自动填 seq、ts。未 init 则静默忽略。"""
    steps = _trace_steps_ctx.get()
    if steps is None:
        return
    step = dict(step)
    step["seq"] = len(steps) + 1
    if "ts" not in step:
        step["ts"] = _now_iso()
    steps.append(step)


def trace_tool_start(name: str) -> None:
    """
    工具即将执行时调用（通常由 tools.hooks.report_tool 触发）。

    用途：记录 perf 开始时间，供 trace_tool_end 计算 duration_ms。
    同名工具可重入（模型重试 list_sql_tables 多次）：用 name / name#2 / name#3 区分，
    并用 _last::{name} 指向最近一次未闭合的 key。
    未 init_trace 时直接返回，不抛错（单测或 CLI 误调安全）。
    """
    pending = _trace_pending_ctx.get()
    if pending is None:
        return
    base = name
    key = base
    n = 1
    while key in pending:
        n += 1
        key = f"{base}#{n}"
    pending[key] = time.perf_counter()
    pending[f"_last::{base}"] = key


def trace_tool_end(
    *,
    tool: str,
    ok: bool,
    role: str = "optional",
    message: str = "",
    error_type: Optional[str] = None,
    retryable: bool = False,
    record_failure: bool = False,
) -> None:
    """
    工具执行结束时调用（format_tool_ok / format_tool_error）。

    用途：
        1. 配对 start，写入一条 kind=tool 的 step（含 duration_ms、role、成败）
        2. 若 record_failure=True 且失败，同步写入 R1 的 failure_steps（供终态决策）

    注意：start/end 必须同名；若只有 end 没有 start，duration_ms 记为 0，仍会落一条 step。
    """
    pending = _trace_pending_ctx.get()
    duration_ms = 0
    if pending is not None:
        last_key = pending.pop(f"_last::{tool}", None)
        start = None
        if isinstance(last_key, str):
            start = pending.pop(last_key, None)
        if start is None:
            for k in list(pending.keys()):
                if k == tool or k.startswith(f"{tool}#"):
                    start = pending.pop(k, None)
                    break
        if start is not None:
            duration_ms = int((time.perf_counter() - float(start)) * 1000)

    _append_step(
        {
            "kind": "tool",
            "name": tool,
            "role": role,
            "status": "ok" if ok else "error",
            "error_type": error_type,
            "message": message if not ok else (message or "ok"),
            "retryable": retryable,
            "duration_ms": duration_ms,
        }
    )

    if record_failure and not ok:
        from context.failure_steps import record_failure_step

        record_failure_step(
            {
                "tool": tool,
                "role": role,
                "message": message,
                "error_type": error_type or "upstream",
                "retryable": retryable,
            }
        )


def trace_event(
    *,
    kind: str,
    name: str,
    status: str = "ok",
    message: str = "",
    **extra: Any,
) -> None:
    """
    记录非「工具起止」类事件（由 runner 调用）。

    常用 kind：
        - session：工作目录创建
        - assistant：主 Agent 委派子 Agent（task 工具）
        - model_result：主模型产出最终说明正文
        - status：任务终态 done / partial_success / error
    """
    payload: Dict[str, Any] = {
        "kind": kind,
        "name": name,
        "status": status,
        "message": message,
        "duration_ms": extra.pop("duration_ms", None),
    }
    payload.update(extra)
    _append_step(payload)


def build_trace_document(
    *,
    status: str,
    failed_steps: Optional[List[Dict[str, Any]]] = None,
    session_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """
    组装完整 Trace 文档（供 write_trace 落盘与 API 返回）。

    顶层字段：thread_id, query, status, session_dir,
              started_at, finished_at, duration_ms, steps, failed_steps
    """
    meta = _trace_meta_ctx.get() or {}
    started_perf = meta.get("started_perf")
    finished_at = _now_iso()
    duration_ms = 0
    if isinstance(started_perf, (int, float)):
        duration_ms = int((time.perf_counter() - float(started_perf)) * 1000)
    return {
        "thread_id": meta.get("thread_id") or "",
        "query": meta.get("query") or "",
        "status": status,
        "session_dir": session_dir,
        "started_at": meta.get("started_at") or finished_at,
        "finished_at": finished_at,
        "duration_ms": duration_ms,
        "steps": get_trace_steps(),
        "failed_steps": list(failed_steps or []),
    }
