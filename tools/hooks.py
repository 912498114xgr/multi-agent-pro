"""
tools/hooks.py — 工具层埋点钩子

默认只在 RUNNER_DEBUG=1 时打印，避免与 Monitor 进度事件双轨刷屏。
子 Agent 内部工具执行不再逐条推 WS（进度由 assistant_call + 终态摘要覆盖）。
"""

from typing import Any, Dict, Optional


class ToolHooks:
    """工具调用观察者（开发调试用）。"""

    def report_tool(self, tool_name: str, args: Optional[Dict[str, Any]] = None) -> None:
        try:
            from config.settings import get_settings
            if not get_settings().runner_debug:
                return
        except Exception:
            return
        print(f"[Tool] {tool_name} args={args or {}}")


hooks = ToolHooks()
