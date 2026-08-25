"""
工具结果结构化协议 + 任务终态决策（R1 失败隔离）。

返回格式（供 LLM 阅读 + 机器解析）::

    [[EA_TOOL_RESULT]]{"ok": false, "tool": "...", "role": "optional", ...}
    <正文>

子 Agent 嵌套时，主图 astream 看不到内部工具原文，因此 format_tool_error
会写入 ContextVar 失败列表，由 runner 在任务结束时 decide_task_status。
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Literal, Optional

from context.failure_steps import record_failure_step

TOOL_RESULT_MARKER = "[[EA_TOOL_RESULT]]"

ToolRole = Literal["critical", "optional"]

# 工具名 → 失败时对整单任务的影响角色
TOOL_ROLES: Dict[str, ToolRole] = {
    "list_sql_tables": "critical",
    "get_table_data": "critical",
    "execute_sql_query": "critical",
    "read_file_content": "critical",
    "generate_markdown": "critical",
    "internet_search": "optional",
    "get_assistant_list": "optional",
    "create_ask_delete": "optional",
    "convert_md_to_pdf": "optional",
}


def role_for_tool(tool: str) -> ToolRole:
    return TOOL_ROLES.get(tool, "optional")


def format_tool_ok(*, tool: str, body: str, role: Optional[ToolRole] = None) -> str:
    """成功：结构化头 + 原始正文（CSV/搜索结果等仍给模型读）。"""
    resolved_role = role or role_for_tool(tool)
    payload = {
        "ok": True,
        "tool": tool,
        "role": resolved_role,
        "error_type": None,
        "retryable": False,
        "message": "ok",
    }
    return f"{TOOL_RESULT_MARKER}{json.dumps(payload, ensure_ascii=False)}\n{body}"


def format_tool_error(
    *,
    tool: str,
    message: str,
    error_type: str = "upstream",
    retryable: bool = False,
    role: Optional[ToolRole] = None,
) -> str:
    """失败：结构化头 + 可读说明；并记入当前协程失败列表。"""
    resolved_role = role or role_for_tool(tool)
    payload = {
        "ok": False,
        "tool": tool,
        "role": resolved_role,
        "error_type": error_type,
        "retryable": retryable,
        "message": message,
    }
    record_failure_step(
        {
            "tool": tool,
            "role": resolved_role,
            "message": message,
            "error_type": error_type,
            "retryable": retryable,
        }
    )
    # 正文保留中文错误形态，便于 Prompt 中「若看到错误/未接入」类规则继续生效
    human = message if message.startswith(("错误", "提示", "网络", "查询", "生成", "转换", "读取", "提问")) else f"错误：{message}"
    return f"{TOOL_RESULT_MARKER}{json.dumps(payload, ensure_ascii=False)}\n{human}"


def parse_tool_result(text: str) -> Optional[Dict[str, Any]]:
    """从工具返回文本中解析结构化头；无标记则返回 None。"""
    if not text or TOOL_RESULT_MARKER not in text:
        return None
    try:
        after = text.split(TOOL_RESULT_MARKER, 1)[1]
        line = after.split("\n", 1)[0].strip()
        data = json.loads(line)
        if not isinstance(data, dict) or "ok" not in data:
            return None
        return data
    except (json.JSONDecodeError, IndexError, TypeError):
        return None


def decide_task_status(failed_steps: List[Dict[str, Any]]) -> Literal["done", "partial_success", "error"]:
    """
    critical 失败 → error
    仅 optional 失败 → partial_success
    无失败 → done
    """
    if not failed_steps:
        return "done"
    if any(step.get("role") == "critical" for step in failed_steps):
        return "error"
    return "partial_success"
