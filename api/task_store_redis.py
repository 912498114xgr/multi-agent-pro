"""
Redis 任务状态存储：与内存 TaskStore 接口一致，支持进程重启后恢复 running 任务列表。
"""

from __future__ import annotations

import datetime
import json
from typing import Any, Dict, List, Optional

import redis

from api.task_store import TaskStatus

_TASK_PREFIX = "efficiency:task:"
_RUNNING_SET = "efficiency:tasks:running"


class RedisTaskStore:
    def __init__(self, redis_url: str) -> None:
        self._redis = redis.Redis.from_url(redis_url, decode_responses=True)

    def _key(self, thread_id: str) -> str:
        return f"{_TASK_PREFIX}{thread_id}"

    def _now(self) -> str:
        return datetime.datetime.now(datetime.timezone.utc).isoformat()

    def _serialize(self, record: Dict[str, Any]) -> str:
        return json.dumps(record, ensure_ascii=False)

    def _deserialize(self, raw: Optional[str]) -> Optional[Dict[str, Any]]:
        if not raw:
            return None
        return json.loads(raw)

    def create(self, thread_id: str, query: str) -> Dict[str, Any]:
        now = self._now()
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
        self._redis.set(self._key(thread_id), self._serialize(record))
        return dict(record)

    def get(self, thread_id: str) -> Optional[Dict[str, Any]]:
        record = self._deserialize(self._redis.get(self._key(thread_id)))
        return dict(record) if record else None

    def _update(self, thread_id: str, **fields: Any) -> Optional[Dict[str, Any]]:
        record = self.get(thread_id)
        if not record:
            return None
        record.update(fields)
        record["updated_at"] = self._now()
        self._redis.set(self._key(thread_id), self._serialize(record))

        if record.get("status") == TaskStatus.RUNNING.value:
            self._redis.sadd(_RUNNING_SET, thread_id)
        else:
            self._redis.srem(_RUNNING_SET, thread_id)

        return dict(record)

    def mark_running(self, thread_id: str) -> Optional[Dict[str, Any]]:
        return self._update(thread_id, status=TaskStatus.RUNNING.value)

    def mark_done(self, thread_id: str, result: str, session_dir: Optional[str] = None) -> Optional[Dict[str, Any]]:
        fields: Dict[str, Any] = {
            "status": TaskStatus.DONE.value,
            "result": result,
            "error": None,
        }
        if session_dir:
            fields["session_dir"] = session_dir
        return self._update(thread_id, **fields)

    def mark_error(self, thread_id: str, error: str) -> Optional[Dict[str, Any]]:
        return self._update(thread_id, status=TaskStatus.ERROR.value, error=error)

    def set_session_dir(self, thread_id: str, session_dir: str) -> Optional[Dict[str, Any]]:
        return self._update(thread_id, session_dir=session_dir)

    def list_running(self) -> List[Dict[str, Any]]:
        thread_ids = self._redis.smembers(_RUNNING_SET)
        tasks: List[Dict[str, Any]] = []
        for thread_id in thread_ids:
            record = self.get(thread_id)
            if record and record.get("status") == TaskStatus.RUNNING.value:
                tasks.append(record)
            else:
                self._redis.srem(_RUNNING_SET, thread_id)
        return tasks
