"""
内存任务状态存储（MVP）。

状态流转：pending -> running -> done | error
"""

from __future__ import annotations

import datetime
import threading
from enum import Enum
from typing import Any, Dict, Optional


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


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

    def mark_done(self, thread_id: str, result: str, session_dir: Optional[str] = None) -> Optional[Dict[str, Any]]:
        fields: Dict[str, Any] = {"status": TaskStatus.DONE.value, "result": result, "error": None}
        if session_dir:
            fields["session_dir"] = session_dir
        return self._update(thread_id, **fields)

    def mark_error(self, thread_id: str, error: str) -> Optional[Dict[str, Any]]:
        return self._update(thread_id, status=TaskStatus.ERROR.value, error=error)

    def set_session_dir(self, thread_id: str, session_dir: str) -> Optional[Dict[str, Any]]:
        return self._update(thread_id, session_dir=session_dir)


task_store = TaskStore()
