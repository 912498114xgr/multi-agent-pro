"""
工具结果结构化协议（R1 失败隔离）+ Trace 收尾（R2）。

================================================================================
用途
================================================================================
1. 所有业务工具统一通过 format_tool_ok / format_tool_error 返回字符串：
   - 不抛异常，避免打断 DeepAgents/LangGraph 图执行（软失败）
   - 首行 [[EA_TOOL_RESULT]]{json} 供机器解析；正文供 LLM 阅读
2. format_* 结束时调用 trace_tool_end：写入步骤级 Trace（耗时/成败/role）
3. 失败时 record_failure=True → 同步 R1 failure_steps → runner 终态决策

================================================================================
TOOL_ROLES（失败时对整单任务的影响）
================================================================================
critical：查库、读上传、写 Markdown → 失败则任务 error（禁止「done + 幻觉报告」）
optional：搜索、RAG、转 PDF → 失败可 partial_success 降级继续

================================================================================
返回串形态示例
================================================================================
[[EA_TOOL_RESULT]]{"ok": false, "tool": "internet_search", "role": "optional", ...}
错误：TAVILY_API_KEY 未配置
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Literal, Optional

from context.trace import trace_tool_end

# 机器可读头标记；parse_tool_result / 模型 Prompt 均依赖此前缀
TOOL_RESULT_MARKER = "[[EA_TOOL_RESULT]]"

ToolRole = Literal["critical", "optional"]

# 工具名 → 失败时对整单任务的影响角色（decide_task_status 间接依赖 failure 里的 role）
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
    """查表得到工具角色；未知工具默认 optional（宁可降级，不轻易整单失败）。"""
    return TOOL_ROLES.get(tool, "optional")


def format_tool_ok(*, tool: str, body: str, role: Optional[ToolRole] = None) -> str:
    """
    工具成功返回。

    - 写 Trace 成功步骤（配对 hooks 的 start，填充 duration_ms）
    - 返回「结构化头 + 原始正文」（CSV/搜索 JSON 等仍给模型读）
    """
    resolved_role = role or role_for_tool(tool)
    payload = {
        "ok": True,
        "tool": tool,
        "role": resolved_role,
        "error_type": None,
        "retryable": False,
        "message": "ok",
    }
    trace_tool_end(tool=tool, ok=True, role=resolved_role, message="ok")
    return f"{TOOL_RESULT_MARKER}{json.dumps(payload, ensure_ascii=False)}\n{body}"


def format_tool_error(
    *,
    tool: str,
    message: str,
    error_type: str = "upstream",
    retryable: bool = False,
    role: Optional[ToolRole] = None,
) -> str:
    """
    工具失败返回（软失败：不抛异常）。

    - 写 Trace 失败步骤
    - 写入 failure_steps（R1），供 runner decide_task_status
    - 正文保留中文错误形态，兼容 Prompt「若看到错误/未接入」类规则
    """
    resolved_role = role or role_for_tool(tool)
    payload = {
        "ok": False,
        "tool": tool,
        "role": resolved_role,
        "error_type": error_type,
        "retryable": retryable,
        "message": message,
    }
    trace_tool_end(
        tool=tool,
        ok=False,
        role=resolved_role,
        message=message,
        error_type=error_type,
        retryable=retryable,
        record_failure=True,
    )
    human = (
        message
        if message.startswith(("错误", "提示", "网络", "查询", "生成", "转换", "读取", "提问"))
        else f"错误：{message}"
    )
    return f"{TOOL_RESULT_MARKER}{json.dumps(payload, ensure_ascii=False)}\n{human}"


def parse_tool_result(text: str) -> Optional[Dict[str, Any]]:
    """
    从工具返回文本解析 [[EA_TOOL_RESULT]] 后的 JSON 头。
    无标记或解析失败返回 None（兼容旧纯文本返回）。
    """
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
    根据失败步骤角色决定任务终态（R1）。

    - 无失败 → done
    - 任一条 role=critical → error（关键路径挂了）
    - 仅 optional → partial_success（可降级完成）
    """
    if not failed_steps:
        return "done"
    if any(step.get("role") == "critical" for step in failed_steps):
        return "error"
    return "partial_success"
