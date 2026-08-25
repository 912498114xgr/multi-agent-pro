"""
任务进度监控：CLI 打印 + WebSocket 推送。

设计原则（日志降噪 + R2）：
  - 进度事件面向用户，宁少勿滥（不把每个 tool_exec 再推 WS）
  - 失败步骤合并为一条 failures_summary
  - 终态事件语义与 status 对齐
  - ConnectionManager 保留每线程最近 N 条事件，WebSocket 重连时补发（replay）
"""

from __future__ import annotations

import asyncio
import datetime
from typing import Any, Dict, List, Optional

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
        """构造 payload → 写入 ring buffer → 推 WS → 控制台一行。"""
        payload = self._build_payload(event_type, message, data)
        if self.websocket_manager:
            tid = payload.get("thread_id") or get_thread_context()
            if tid:
                # R2：先入缓冲，保证重连时能补发（即便当时无连接也能事后连上看到历史）
                self.websocket_manager.record_event(str(tid), payload)
        self._send_payload_to_websocket(payload)
        print(f"\n[Monitor:{event_type}] {message}")

    def _build_payload(self, event_type: str, message: str, data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        return {
            "type": "monitor_event",
            "event": event_type,
            "message": message,
            "data": data or {},
            "thread_id": get_thread_context(),
            "timestamp": datetime.datetime.now().isoformat(),
        }

    def _send_payload_to_websocket(self, payload: Dict[str, Any]) -> None:
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
        """主 Agent 规划调用工具时（来自 astream tool_calls，不是子 Agent 内部执行）。"""
        self._emit("tool_start", f"准备调用工具: {tool_name}", {"tool_name": tool_name, "args": args or {}})

    def report_assistant(self, assistant_name: str, args: Dict[str, Any] = None) -> None:
        self._emit("assistant_call", f"正在调用助手: {assistant_name}", {
            "assistant_name": assistant_name,
            "args": args or {},
        })

    def report_task_result(self, result: str) -> None:
        """模型已产出说明性正文；真正终态由 done / partial_success / error 决定。"""
        self._emit(
            "task_result",
            "模型已生成回复（等待任务终态确认）",
            {"result": result},
        )

    def report_session_dir(self, path: str) -> None:
        self._emit("session_created", f"工作目录已创建: {path}", {"path": path})

    def report_failures_summary(self, failed_steps: List[Dict[str, Any]]) -> None:
        """合并失败步骤为一条进度事件，避免逐条刷屏。"""
        if not failed_steps:
            return
        critical_n = sum(1 for s in failed_steps if s.get("role") == "critical")
        optional_n = len(failed_steps) - critical_n
        by_tool: Dict[str, int] = {}
        for s in failed_steps:
            name = str(s.get("tool") or "unknown")
            by_tool[name] = by_tool.get(name, 0) + 1
        tool_bits = ", ".join(f"{k}×{v}" if v > 1 else k for k, v in by_tool.items())
        msg = (
            f"工具失败汇总: 共 {len(failed_steps)} 次"
            f"（关键 {critical_n} / 可选 {optional_n}）— {tool_bits}"
        )
        self._emit(
            "failures_summary",
            msg,
            {
                "failed_steps": failed_steps,
                "critical_count": critical_n,
                "optional_count": optional_n,
                "by_tool": by_tool,
            },
        )

    def report_degraded(self, failed_steps: list, status: str) -> None:
        """可选能力失败后的降级终态（通常 partial_success）。"""
        label = "部分成功" if status == "partial_success" else status
        self._emit(
            "degraded",
            f"任务终态: {label}（可选能力失败已降级）",
            {"status": status, "failed_steps": failed_steps},
        )

    def report_error(self, message: str, failed_steps: Optional[List[Dict[str, Any]]] = None) -> None:
        """关键失败或未捕获异常导致的任务 error。"""
        self._emit(
            "error",
            message,
            {"failed_steps": failed_steps or []},
        )

    def report_timeout(self, message: str) -> None:
        """R3：整任务超时。"""
        self._emit("timeout", message, {"status": "timeout"})

    def report_cancelled(self, message: str = "任务已取消") -> None:
        """R3：任务取消。"""
        self._emit("cancelled", message, {"status": "cancelled"})


monitor = ToolMonitor()


class ConnectionManager:
    """
    WebSocket 连接管理：按 thread_id 定向推送。

    R2 增强：
        - 每线程 ring buffer（EVENT_BUFFER_SIZE）保存近期 monitor 事件
        - connect 成功后按序补发，payload.replay=true，前端可忽略重复展示
    """

    EVENT_BUFFER_SIZE = 50

    def __init__(self) -> None:
        self.active_connections: Dict[str, WebSocket] = {}
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        # thread_id → 最近 N 条 monitor_event
        self._event_buffers: Dict[str, List[Dict[str, Any]]] = {}

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop
        monitor.set_websocket_manager(self)
        print(f"[Monitor] ConnectionManager bound to loop: {id(self.loop)}")

    def record_event(self, thread_id: str, payload: Dict[str, Any]) -> None:
        """写入该 thread 的事件缓冲（超出容量丢弃最旧）。"""
        buf = self._event_buffers.setdefault(thread_id, [])
        stored = dict(payload)
        stored["replay"] = False
        buf.append(stored)
        if len(buf) > self.EVENT_BUFFER_SIZE:
            del buf[: len(buf) - self.EVENT_BUFFER_SIZE]

    async def connect(self, websocket: WebSocket, thread_id: str) -> None:
        await websocket.accept()
        self.active_connections[thread_id] = websocket
        print(f"[Monitor] Client connected: {thread_id}")
        # 重连补发：让前端尽快对齐进度（完整时间线仍以 Trace API 为准）
        for event in list(self._event_buffers.get(thread_id, [])):
            replay_payload = dict(event)
            replay_payload["replay"] = True
            try:
                await websocket.send_json(replay_payload)
            except Exception:
                break

    def disconnect(self, websocket: WebSocket, thread_id: str) -> None:
        if self.active_connections.get(thread_id) is websocket:
            del self.active_connections[thread_id]
        print(f"[Monitor] Client disconnected: {thread_id}")

    async def send_to_thread(self, message: dict, thread_id: str) -> None:
        websocket = self.active_connections.get(thread_id)
        if websocket:
            await websocket.send_json(message)


manager = ConnectionManager()
