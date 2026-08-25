"""
任务状态存储（MVP 内存实现）。

状态流转：pending -> running -> done | partial_success | error | timeout | cancelled
"""

from __future__ import annotations

import datetime
import threading
from enum import Enum
from typing import Any, Dict, List, Optional


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    PARTIAL_SUCCESS = "partial_success"
    ERROR = "error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class TaskStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tasks: Dict[str, Dict[str, Any]] = {}

    def create(self, thread_id: str, query: str) -> Dict[str, Any]:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        record = {
            "thread_id": thread_id,
            "query": query,
            "status": TaskStatus.PENDING.value,
            "result": None,
            "error": None,
            "session_dir": None,
            "failed_steps": [],
            # R2：完整步骤时间线与落盘路径（任务结束后由 runner 填充）
            "steps": [],
            "trace_path": None,
            "created_at": now,
            "updated_at": now,
        }
        with self._lock:
            self._tasks[thread_id] = record
        return dict(record)

    def get(self, thread_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            task = self._tasks.get(thread_id)
            return dict(task) if task else None

    def _update(self, thread_id: str, **fields: Any) -> Optional[Dict[str, Any]]:
        with self._lock:
            task = self._tasks.get(thread_id)
            if not task:
                return None
            task.update(fields)
            task["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            return dict(task)

    def mark_running(self, thread_id: str) -> Optional[Dict[str, Any]]:
        return self._update(thread_id, status=TaskStatus.RUNNING.value)

    def mark_done(
        self,
        thread_id: str,
        result: str,
        session_dir: Optional[str] = None,
        steps: Optional[List[Dict[str, Any]]] = None,
        trace_path: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        fields: Dict[str, Any] = {
            "status": TaskStatus.DONE.value,
            "result": result,
            "error": None,
            "failed_steps": [],
        }
        if session_dir:
            fields["session_dir"] = session_dir
        if steps is not None:
            fields["steps"] = list(steps)
        if trace_path is not None:
            fields["trace_path"] = trace_path
        return self._update(thread_id, **fields)

    def mark_partial_success(
        self,
        thread_id: str,
        result: str,
        failed_steps: List[Dict[str, Any]],
        session_dir: Optional[str] = None,
        steps: Optional[List[Dict[str, Any]]] = None,
        trace_path: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        fields: Dict[str, Any] = {
            "status": TaskStatus.PARTIAL_SUCCESS.value,
            "result": result,
            "error": None,
            "failed_steps": list(failed_steps),
        }
        if session_dir:
            fields["session_dir"] = session_dir
        if steps is not None:
            fields["steps"] = list(steps)
        if trace_path is not None:
            fields["trace_path"] = trace_path
        return self._update(thread_id, **fields)

    def mark_error(
        self,
        thread_id: str,
        error: str,
        failed_steps: Optional[List[Dict[str, Any]]] = None,
        steps: Optional[List[Dict[str, Any]]] = None,
        trace_path: Optional[str] = None,
        session_dir: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        fields: Dict[str, Any] = {
            "status": TaskStatus.ERROR.value,
            "error": error,
        }
        if failed_steps is not None:
            fields["failed_steps"] = list(failed_steps)
        if steps is not None:
            fields["steps"] = list(steps)
        if trace_path is not None:
            fields["trace_path"] = trace_path
        if session_dir is not None:
            fields["session_dir"] = session_dir
        return self._update(thread_id, **fields)

    def mark_timeout(
        self,
        thread_id: str,
        error: str = "任务执行超时",
        steps: Optional[List[Dict[str, Any]]] = None,
        trace_path: Optional[str] = None,
        session_dir: Optional[str] = None,
        failed_steps: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[Dict[str, Any]]:
        """R3：整任务 asyncio.wait_for 超时。"""
        fields: Dict[str, Any] = {
            "status": TaskStatus.TIMEOUT.value,
            "error": error,
        }
        if steps is not None:
            fields["steps"] = list(steps)
        if trace_path is not None:
            fields["trace_path"] = trace_path
        if session_dir is not None:
            fields["session_dir"] = session_dir
        if failed_steps is not None:
            fields["failed_steps"] = list(failed_steps)
        return self._update(thread_id, **fields)

    def mark_cancelled(
        self,
        thread_id: str,
        error: str = "任务已取消",
        steps: Optional[List[Dict[str, Any]]] = None,
        trace_path: Optional[str] = None,
        session_dir: Optional[str] = None,
        failed_steps: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[Dict[str, Any]]:
        """R3：客户端取消或 Task.cancel()。"""
        fields: Dict[str, Any] = {
            "status": TaskStatus.CANCELLED.value,
            "error": error,
        }
        if steps is not None:
            fields["steps"] = list(steps)
        if trace_path is not None:
            fields["trace_path"] = trace_path
        if session_dir is not None:
            fields["session_dir"] = session_dir
        if failed_steps is not None:
            fields["failed_steps"] = list(failed_steps)
        return self._update(thread_id, **fields)

    def set_session_dir(self, thread_id: str, session_dir: str) -> Optional[Dict[str, Any]]:
        return self._update(thread_id, session_dir=session_dir)

    def set_trace(
        self,
        thread_id: str,
        *,
        steps: List[Dict[str, Any]],
        trace_path: str,
    ) -> Optional[Dict[str, Any]]:
        """R2：单独更新 steps / trace_path（也可由 mark_* 一并写入）。"""
        return self._update(thread_id, steps=list(steps), trace_path=trace_path)


task_store = TaskStore()
