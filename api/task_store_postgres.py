"""
R6b：PostgreSQL 任务状态存储 — 多实例可共享，与 LangGraph checkpoint 同库不同表。
"""

from __future__ import annotations

import datetime
import json
import threading
from typing import Any, Dict, List, Optional

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from api.task_store import TaskStatus

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS tasks (
    thread_id TEXT PRIMARY KEY,
    query TEXT NOT NULL,
    status TEXT NOT NULL,
    result TEXT,
    error TEXT,
    session_dir TEXT,
    failed_steps TEXT NOT NULL DEFAULT '[]',
    steps TEXT NOT NULL DEFAULT '[]',
    trace_path TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _json_loads(text: Optional[str], default: Any) -> Any:
    if not text:
        return default
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return default


class PostgresTaskStore:
    """与 TaskStore 相同的方法签名，底层 PostgreSQL 持久化。"""

    def __init__(self, database_url: str) -> None:
        self._pool = ConnectionPool(
            conninfo=database_url,
            min_size=1,
            max_size=5,
            kwargs={"autocommit": True, "row_factory": dict_row},
        )
        self._lock = threading.Lock()
        with self._pool.connection() as conn:
            conn.execute(_CREATE_SQL)

    def _row_to_dict(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "thread_id": row["thread_id"],
            "query": row["query"],
            "status": row["status"],
            "result": row["result"],
            "error": row["error"],
            "session_dir": row["session_dir"],
            "failed_steps": _json_loads(row["failed_steps"], []),
            "steps": _json_loads(row["steps"], []),
            "trace_path": row["trace_path"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def create(self, thread_id: str, query: str) -> Dict[str, Any]:
        now = _now_iso()
        record = {
            "thread_id": thread_id,
            "query": query,
            "status": TaskStatus.PENDING.value,
            "result": None,
            "error": None,
            "session_dir": None,
            "failed_steps": [],
            "steps": [],
            "trace_path": None,
            "created_at": now,
            "updated_at": now,
        }
        with self._lock:
            with self._pool.connection() as conn:
                conn.execute(
                    """
                    INSERT INTO tasks (
                        thread_id, query, status, result, error, session_dir,
                        failed_steps, steps, trace_path, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        thread_id,
                        query,
                        record["status"],
                        None,
                        None,
                        None,
                        _json_dumps([]),
                        _json_dumps([]),
                        None,
                        now,
                        now,
                    ),
                )
        return dict(record)

    def get(self, thread_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            with self._pool.connection() as conn:
                cur = conn.execute(
                    "SELECT * FROM tasks WHERE thread_id = %s", (thread_id,)
                )
                row = cur.fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    def list_tasks(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        with self._lock:
            with self._pool.connection() as conn:
                cur = conn.execute(
                    "SELECT * FROM tasks ORDER BY updated_at DESC LIMIT %s OFFSET %s",
                    (limit, offset),
                )
                rows = cur.fetchall()
        return [self._row_to_dict(row) for row in rows]

    def _update(self, thread_id: str, **fields: Any) -> Optional[Dict[str, Any]]:
        if not fields:
            return self.get(thread_id)
        fields["updated_at"] = _now_iso()
        sets: List[str] = []
        values: List[Any] = []
        for key, val in fields.items():
            if key in ("failed_steps", "steps") and val is not None:
                val = _json_dumps(val)
            sets.append(f"{key} = %s")
            values.append(val)
        values.append(thread_id)
        sql = f"UPDATE tasks SET {', '.join(sets)} WHERE thread_id = %s"
        with self._lock:
            with self._pool.connection() as conn:
                cur = conn.execute(sql, values)
                if cur.rowcount == 0:
                    return None
        return self.get(thread_id)

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
        return self._update(thread_id, steps=list(steps), trace_path=trace_path)

    def close(self) -> None:
        self._pool.close()
