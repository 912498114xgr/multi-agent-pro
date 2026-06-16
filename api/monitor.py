import asyncio
import datetime
from typing import Any, Dict, Optional

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
        payload = {
            "type": "monitor_event",
            "event": event_type,
            "message": message,
            "data": data or {},
            "thread_id": get_thread_context(),
            "timestamp": datetime.datetime.now().isoformat(),
        }

        if self.websocket_manager:
            try:
                thread_id = get_thread_context()
                manager_loop = self.websocket_manager.loop
                if manager_loop and thread_id:
                    try:
                        current_loop = asyncio.get_running_loop()
                    except RuntimeError:
                        current_loop = None

                    if current_loop and current_loop == manager_loop:
                        current_loop.create_task(
                            self.websocket_manager.send_to_thread(payload, thread_id)
                        )
                    else:
                        asyncio.run_coroutine_threadsafe(
                            self.websocket_manager.send_to_thread(payload, thread_id),
                            manager_loop,
                        )
            except Exception as e:
                print(f"[Monitor] WebSocket send failed: {e}")

        print(f"[Monitor:{event_type}] {message}")

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


monitor = ToolMonitor()
