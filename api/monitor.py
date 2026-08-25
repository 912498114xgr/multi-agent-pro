import asyncio
import datetime
from typing import Any, Dict, Optional

from fastapi import WebSocket

from context.session import get_thread_context


class ToolMonitor:
    """任务进度监控：CLI 模式打印到控制台；API 模式可对接 WebSocket。"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.websocket_manager = None
        return cls._instance

    def set_websocket_manager(self, manager) -> None:
        self.websocket_manager = manager

    def _emit(self, event_type: str, message: str, data: Optional[Dict[str, Any]] = None) -> None:
        payload = self._build_payload(event_type, message, data)
        self._send_payload_to_websocket(payload)
        print(f"\n[Monitor:{event_type}] {message}")

    def _build_payload(self, event_type: str, message: str, data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """统一的前端进度事件格式。"""
        return {
            "type": "monitor_event",
            "event": event_type,
            "message": message,
            "data": data or {},
            "thread_id": get_thread_context(),
            "timestamp": datetime.datetime.now().isoformat(),
        }

    def _send_payload_to_websocket(self, payload: Dict[str, Any]) -> None:
        """把进度事件投递给当前 thread_id 对应的 WebSocket。"""
        if not self.websocket_manager:
            return

        thread_id = get_thread_context()
        manager_loop = self.websocket_manager.loop
        if not thread_id or not manager_loop:
            return

        try:
            self._schedule_websocket_send(payload, thread_id, manager_loop)
        except Exception as e:
            print(f"[Monitor] WebSocket send failed: {e}")

    def _schedule_websocket_send(
        self,
        payload: Dict[str, Any],
        thread_id: str,
        manager_loop: asyncio.AbstractEventLoop,
    ) -> None:
        """
        WebSocket 发送必须交给 FastAPI 的 event loop。

        同一个 loop 内直接 create_task；跨线程或无 running loop 时，用线程安全方式投递。
        """
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        send_coro = self.websocket_manager.send_to_thread(payload, thread_id)
        if current_loop and current_loop == manager_loop:
            current_loop.create_task(send_coro)
        else:
            asyncio.run_coroutine_threadsafe(send_coro, manager_loop)

    def report_tool(self, tool_name: str, args: Dict[str, Any] = None) -> None:
        self._emit("tool_start", f"开始执行工具: {tool_name}", {"tool_name": tool_name, "args": args})

    def report_assistant(self, assistant_name: str, args: Dict[str, Any] = None) -> None:
        self._emit("assistant_call", f"正在调用助手: {assistant_name}", {
            "assistant_name": assistant_name,
            "args": args,
        })

    def report_task_result(self, result: str) -> None:
        self._emit("task_result", "任务执行完成", {"result": result})

    def report_session_dir(self, path: str) -> None:
        self._emit("session_created", f"工作目录已创建: {path}", {"path": path})

    def report_step_failed(self, step: Dict[str, Any]) -> None:
        tool = step.get("tool", "unknown")
        role = step.get("role", "optional")
        message = step.get("message", "")
        self._emit(
            "step_failed",
            f"步骤失败({role}): {tool} — {message}",
            {"step": step},
        )

    def report_degraded(self, failed_steps: list, status: str) -> None:
        self._emit(
            "degraded",
            f"任务降级完成: status={status}, failed={len(failed_steps)}",
            {"status": status, "failed_steps": failed_steps},
        )


monitor = ToolMonitor()


class ConnectionManager:
    """WebSocket 连接管理：按 thread_id 定向推送 monitor 事件。"""

    def __init__(self) -> None:
        self.active_connections: Dict[str, WebSocket] = {}
        self.loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop
        monitor.set_websocket_manager(self)
        print(f"[Monitor] ConnectionManager bound to loop: {id(self.loop)}")

    async def connect(self, websocket: WebSocket, thread_id: str) -> None:
        await websocket.accept()
        self.active_connections[thread_id] = websocket
        print(f"[Monitor] Client connected: {thread_id}")

    def disconnect(self, websocket: WebSocket, thread_id: str) -> None:
        if self.active_connections.get(thread_id) is websocket:
            del self.active_connections[thread_id]
        print(f"[Monitor] Client disconnected: {thread_id}")

    async def send_to_thread(self, message: dict, thread_id: str) -> None:
        websocket = self.active_connections.get(thread_id)
        if websocket:
            await websocket.send_json(message)


manager = ConnectionManager()
