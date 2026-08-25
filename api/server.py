"""
EfficiencyAgent FastAPI 服务：任务提交、状态查询、文件上传、WebSocket 进度推送。
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path
from typing import List, Optional

import uvicorn
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from agent.mainagent.runner import run_deep_agent
from api.monitor import manager, monitor
from api.task_store import task_store
from config.settings import get_settings

_settings = get_settings()
app = FastAPI(title="EfficiencyAgent API")

# R3：thread_id → 后台 asyncio.Task，供超时 wait_for 与 cancel API
_running_tasks: dict[str, asyncio.Task] = {}

app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origin_list or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

output_dir = _settings.output_dir
output_dir.mkdir(parents=True, exist_ok=True)
upload_root = _settings.upload_dir
upload_root.mkdir(parents=True, exist_ok=True)


class _SuppressTaskPollAccessLog(logging.Filter):
    """前端轮询 GET /api/tasks/{id} 频率高，默认不打 access，避免刷屏。"""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:
            return True
        if "GET /api/tasks/" in msg and "HTTP" in msg:
            # 保留明显错误码；2xx/404 探针与轮询静音
            if " 200 " in msg or " 404 " in msg:
                return False
        return True


def verify_api_key(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")) -> None:
    expected = _settings.api_key
    if expected and x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")


class TaskRequest(BaseModel):
    query: str = Field(..., min_length=1)
    thread_id: Optional[str] = None


class TaskResponse(BaseModel):
    status: str
    thread_id: str


@app.on_event("startup")
async def startup_event() -> None:
    loop = asyncio.get_running_loop()
    manager.set_loop(loop)
    logging.getLogger("uvicorn.access").addFilter(_SuppressTaskPollAccessLog())


async def _run_task_background(query: str, thread_id: str) -> None:
    """后台 Task：wait_for 整任务超时；CancelledError 区分取消。"""
    timeout_sec = float(_settings.task_timeout_sec)
    try:
        await asyncio.wait_for(run_deep_agent(query, thread_id), timeout=timeout_sec)
    except asyncio.TimeoutError:
        msg = f"任务超过 {int(timeout_sec)}s 未完成（task_timeout_sec）"
        task = task_store.get(thread_id) or {}
        task_store.mark_timeout(
            thread_id,
            error=msg,
            session_dir=task.get("session_dir"),
            steps=task.get("steps"),
            trace_path=task.get("trace_path"),
            failed_steps=task.get("failed_steps"),
        )
        monitor.report_timeout(msg)
        print(f"[API] Task timeout: thread_id={thread_id}")
    except asyncio.CancelledError:
        task = task_store.get(thread_id) or {}
        if task.get("status") in (None, "pending", "running", "cancelled"):
            # runner 可能已 mark_cancelled；若仍 running 则补写
            if task.get("status") != "cancelled":
                task_store.mark_cancelled(
                    thread_id,
                    error="任务已取消",
                    session_dir=task.get("session_dir"),
                    steps=task.get("steps"),
                    trace_path=task.get("trace_path"),
                    failed_steps=task.get("failed_steps"),
                )
                monitor.report_cancelled("任务已取消")
        print(f"[API] Task cancelled: thread_id={thread_id}")
    except Exception as exc:
        # run_deep_agent 内部已经 mark_error；这里兜底
        print(f"[API] Background task failed: thread_id={thread_id}, error={exc}")
    finally:
        _running_tasks.pop(thread_id, None)


def _schedule_agent_task(query: str, thread_id: str) -> None:
    """
    把 Agent 协程登记到当前 FastAPI event loop。

    注意：这里不 await。HTTP 请求只负责“安排后台任务”，不等待 Agent 跑完。
    """
    task = asyncio.create_task(
        _run_task_background(query, thread_id),
        name=f"agent-task-{thread_id}",
    )
    _running_tasks[thread_id] = task


def _start_task(request: TaskRequest) -> TaskResponse:
    """创建任务记录，并安排后台 Agent 执行。"""
    thread_id = request.thread_id or str(uuid.uuid4())
    task_store.create(thread_id, request.query)
    _schedule_agent_task(request.query, thread_id)
    return TaskResponse(status="started", thread_id=thread_id)


@app.post("/api/tasks", response_model=TaskResponse, dependencies=[Depends(verify_api_key)])
async def create_task(request: TaskRequest) -> TaskResponse:
    return _start_task(request)


@app.post("/api/task", response_model=TaskResponse, dependencies=[Depends(verify_api_key)])
async def create_task_compat(request: TaskRequest) -> TaskResponse:
    """兼容 deep_search_pro 路径。"""
    return _start_task(request)


@app.post("/api/tasks/{thread_id}/cancel", dependencies=[Depends(verify_api_key)])
async def cancel_task(thread_id: str):
    """R3：取消进行中的任务。"""
    task = task_store.get(thread_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    status = task.get("status")
    if status not in ("pending", "running"):
        raise HTTPException(status_code=409, detail=f"任务已结束（status={status}），无法取消")
    running = _running_tasks.get(thread_id)
    if running and not running.done():
        running.cancel()
        return {"status": "cancelling", "thread_id": thread_id}
    task_store.mark_cancelled(thread_id, error="任务已取消")
    monitor.report_cancelled("任务已取消")
    return {"status": "cancelled", "thread_id": thread_id}


@app.get("/api/tasks/{thread_id}", dependencies=[Depends(verify_api_key)])
async def get_task(thread_id: str):
    task = task_store.get(thread_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.get("/api/tasks/{thread_id}/trace", dependencies=[Depends(verify_api_key)])
async def get_task_trace(thread_id: str):
    """
    R2：返回完整 Trace 文档，供前端「执行 Trace」面板与面试演示。

    优先读 task.trace_path 指向的 trace.json；
    文件不存在时回退为内存中的 steps / failed_steps 组装（进程未重启时尚可用）。
    """
    task = task_store.get(thread_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    trace_path = task.get("trace_path")
    if trace_path:
        path = Path(trace_path)
        if path.is_file():
            try:
                from observability.trace_io import read_trace
                return read_trace(path)
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"读取 trace 失败: {exc}") from exc

    return {
        "thread_id": thread_id,
        "query": task.get("query"),
        "status": task.get("status"),
        "session_dir": task.get("session_dir"),
        "steps": task.get("steps") or [],
        "failed_steps": task.get("failed_steps") or [],
        "trace_path": trace_path,
    }


@app.post("/api/upload", dependencies=[Depends(verify_api_key)])
async def upload_files(
    files: List[UploadFile] = File(...),
    thread_id: str = Form(...),
):
    target_dir = upload_root / f"session_{thread_id}"
    target_dir.mkdir(parents=True, exist_ok=True)

    saved_files: list[str] = []
    for file in files:
        content = await file.read()
        if len(content) > _settings.max_upload_bytes:
            raise HTTPException(status_code=413, detail=f"File {file.filename} exceeds upload limit")
        file_path = target_dir / file.filename
        with file_path.open("wb") as buffer:
            buffer.write(content)
        saved_files.append(file.filename)

    return {"status": "uploaded", "files": saved_files, "thread_id": thread_id}


@app.get("/api/download", dependencies=[Depends(verify_api_key)])
async def download_file(path: str):
    try:
        abs_path = Path(path).resolve()
        output_abs = output_dir.resolve()
        if not abs_path.is_relative_to(output_abs):
            raise HTTPException(status_code=403, detail="只能下载 output 目录下的文件")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"无效路径: {exc}") from exc

    if not abs_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(abs_path, filename=abs_path.name)


@app.get("/api/files", dependencies=[Depends(verify_api_key)])
async def list_files(path: str):
    try:
        abs_path = Path(path).resolve()
        output_abs = output_dir.resolve()
        if not abs_path.is_relative_to(output_abs):
            raise HTTPException(status_code=403, detail="只能访问 output 目录")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"无效路径: {exc}") from exc

    if not abs_path.exists():
        raise HTTPException(status_code=404, detail="目录不存在")

    files = []
    for file_path in abs_path.rglob("*"):
        if file_path.is_file():
            stat = file_path.stat()
            files.append({
                "name": file_path.name,
                "type": "file",
                "path": str(file_path),
                "size": stat.st_size,
                "mtime": stat.st_mtime,
            })
    files.sort(key=lambda x: x.get("mtime", 0), reverse=True)
    return {"files": files}


@app.websocket("/ws/{thread_id}")
async def websocket_endpoint(websocket: WebSocket, thread_id: str):
    await manager.connect(websocket, thread_id)
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_json({
                "type": "pong",
                "message": f"服务端已收到: {data}",
                "thread_id": thread_id,
            })
    except WebSocketDisconnect:
        manager.disconnect(websocket, thread_id)
    except Exception:
        manager.disconnect(websocket, thread_id)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "EfficiencyAgent"}


if __name__ == "__main__":
    uvicorn.run("api.server:app", host="0.0.0.0", port=8000, reload=True)
