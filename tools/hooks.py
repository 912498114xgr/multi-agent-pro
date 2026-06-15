"""
tools/hooks.py — 工具层埋点钩子

每个 @tool 执行时调用 hooks.report_tool()，用于：
  - 开发阶段：print 到控制台，方便调试
  - 生产阶段：替换为 api.monitor.monitor，向前端 WebSocket 推送进度

替换方式（Phase 5 实现 monitor 后）：
  from api.monitor import monitor as hooks  # 或改 hooks 内部实现
"""

from typing import Any, Dict, Optional


class ToolHooks:
    """工具调用观察者。后续可扩展为写入 task_store 事件列表。"""

    def report_tool(self, tool_name: str, args: Optional[Dict[str, Any]] = None) -> None:
        print(f"[Tool] {tool_name} args={args or {}}")


# 全项目共用的单例，工具文件 from tools.hooks import hooks
hooks = ToolHooks()
