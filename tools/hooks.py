"""
tools/hooks.py — 工具层埋点钩子

用途分层：
    1. 【R2 Trace】每个 @tool 开头调用 report_tool → trace_tool_start
       这样嵌套子 Agent 内的工具也能记耗时（主 Agent astream 看不到子图 tools 节点）。
    2. 【调试打印】仅当 RUNNER_DEBUG=1 时 print，避免与 Monitor WS 进度双轨刷屏。

调用方：
    tools/db_tools.py、tavily_tool.py、ragflow_tools.py、upload_file_read_tool.py、
    markdown_tools.py、pdf_tools.py 等在函数入口 hooks.report_tool(...)

配对：
    工具返回时 format_tool_ok / format_tool_error → trace_tool_end（见 tools/tool_result.py）
"""

from typing import Any, Dict, Optional


class ToolHooks:
    """
    工具调用观察者（进程内单例 hooks）。

    不向 WebSocket 推送每条工具执行（日志降噪）；进度靠 assistant_call + 终态摘要，
    完整时间线靠 Trace 落盘 / API。
    """

    def report_tool(self, tool_name: str, args: Optional[Dict[str, Any]] = None) -> None:
        """
        工具开始执行时调用。

        - 始终尝试 trace_tool_start（未 init_trace 时内部 no-op）
        - 可选 debug 打印工具名与参数
        """
        try:
            from context.trace import trace_tool_start
            trace_tool_start(tool_name)
        except Exception:
            # Trace 模块异常不应打断业务工具
            pass
        try:
            from config.settings import get_settings
            if get_settings().runner_debug:
                print(f"[Tool] {tool_name} args={args or {}}")
        except Exception:
            pass


# 全项目共用单例：from tools.hooks import hooks
hooks = ToolHooks()
