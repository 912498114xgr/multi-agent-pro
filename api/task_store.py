"""
任务状态存储：内存（默认）或 Redis（配置 REDIS_URL 时）。
"""

from __future__ import annotations

import datetime
import threading
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol

from config.settings import get_settings


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


class TaskStoreProtocol(Protocol):
    def create(self, thread_id: str, query: str) -> Dict[str, Any]: ...
    def get(self, thread_id: str) -> Optional[Dict[str, Any]]: ...
    def mark_running(self, thread_id: str) -> Optional[Dict[str, Any]]: ...
    def mark_done(self, thread_id: str, result: str, session_dir: Optional[str] = None) -> Optional[Dict[str, Any]]: ...
    def mark_error(self, thread_id: str, error: str) -> Optional[Dict[str, Any]]: ...
    def set_session_dir(self, thread_id: str, session_dir: str) -> Optional[Dict[str, Any]]: ...
    def list_running(self) -> List[Dict[str, Any]]: ...


class InMemoryTaskStore:
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

    def list_running(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                dict(task)
                for task in self._tasks.values()
                if task.get("status") == TaskStatus.RUNNING.value
            ]


_task_store: Optional[TaskStoreProtocol] = None


def get_task_store() -> TaskStoreProtocol:
    global _task_store
    if _task_store is None:
        settings = get_settings()
        if settings.use_redis_task_store:
            from api.task_store_redis import RedisTaskStore

            _task_store = RedisTaskStore(settings.redis_url)
        else:
            _task_store = InMemoryTaskStore()
    return _task_store


# 向后兼容：from api.task_store import task_store
task_store = get_task_store()
