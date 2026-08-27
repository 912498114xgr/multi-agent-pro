"""
EfficiencyAgent 主 Agent：效能负责人。

- 组装 create_deep_agent + 5 个子 Agent
- run_deep_agent：会话目录、ContextVar、astream 进度推送、Trace 落盘（R2）
"""

import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional
import asyncio

from deepagents.graph import create_deep_agent

from agent.checkpointer import get_checkpointer
from agent.subagent import ALL_SUBAGENTS
from api.monitor import monitor
from api.task_store import task_store
from config.settings import get_settings
from context.failure_steps import get_failure_steps, init_failure_steps, reset_failure_steps
from context.retry_gate import init_retry_gate, reset_retry_gate
from context.session import reset_all_tokens, setup_request_context
from context.trace import (
    build_trace_document,
    get_trace_steps,
    init_trace,
    reset_trace,
    trace_event,
)
from llm.model import model
from observability.logging import get_logger, log_error
from observability.trace_io import write_trace
from prompt.loader import get_main_agent_prompt
from tools.tool_result import decide_task_status
from tools.upload_file_read_tool import read_file_content

_main_cfg = get_main_agent_prompt()
_settings = get_settings()
_project_root = _settings.project_root
_logger = get_logger("runner")

_main_agent = None


async def get_main_agent():
    """R6b：checkpointer 在 lifespan 初始化后再编译 Agent。"""
    global _main_agent
    if _main_agent is None:
        _main_agent = create_deep_agent(
            model=model,
            system_prompt=_main_cfg["system_prompt"],
            tools=[read_file_content],
            checkpointer=get_checkpointer(),
            subagents=ALL_SUBAGENTS,
        )
    return _main_agent


def reset_main_agent_for_tests() -> None:
    """单测重置已编译 Agent。"""
    global _main_agent
    _main_agent = None


def _dbg(*args: Any) -> None:
    if _settings.runner_debug:
        print(*args)


def _log(event: str, message: str = "", **extra: Any) -> None:
    if _settings.runner_debug:
        from observability.logging import log_info
        log_info(_logger, event, message, **extra)


def _prepare_session(session_id: str) -> tuple[Path, str, str, str, list[str]]:
    session_dir = _settings.output_dir / f"session_{session_id}"
    session_dir.mkdir(parents=True, exist_ok=True)

    session_dir_str = str(session_dir.resolve()).replace("\\", "/")
    relative_session_dir_str = str(session_dir.relative_to(_project_root)).replace("\\", "/")

    uploaded_files: list[str] = []
    upload_prompt = ""
    upload_dir = _settings.upload_dir / f"session_{session_id}"
    if upload_dir.exists():
        uploaded_files = [f.name for f in upload_dir.iterdir() if f.is_file()]
        if uploaded_files:
            for filename in uploaded_files:
                shutil.copy2(upload_dir / filename, session_dir / filename)
            upload_prompt = (
                "\n    [已上传文件] 已加载到工作目录:\n"
                + "\n".join(f"    - {f}" for f in uploaded_files)
                + "\n    请优先使用 read_file_content 读取并参考这些文件。"
            )

    return session_dir, session_dir_str, relative_session_dir_str, upload_prompt, uploaded_files


def _build_path_instruction(relative_session_dir: str, upload_prompt: str) -> str:
    return f"""
    【工作环境指令】
    工作目录: {relative_session_dir}
    {upload_prompt}

    规则：
    1. 新生成文件必须保存到工作目录：'{relative_session_dir}/filename'
    2. 读取已上传文件时，filename 只传文件名，不带目录前缀
    3. 使用相对路径，禁止使用绝对路径
    4. 若存在上传文件，请先分析内容
    """


def _tool_call_name(tool_call: Any) -> str:
    if isinstance(tool_call, dict):
        return tool_call.get("name", "")
    return getattr(tool_call, "name", "") or ""


def _tool_call_args(tool_call: Any) -> dict:
    if isinstance(tool_call, dict):
        return tool_call.get("args") or {}
    return getattr(tool_call, "args", None) or {}


def _extract_latest_message(node_name: str, state: Any) -> Any | None:
    _dbg(f"node_name: {node_name}")
    _dbg(f"state: {state}")
    if not state or "messages" not in state:
        return None

    messages = state["messages"]
    _dbg(f"messages_count: {len(messages) if isinstance(messages, list) else 'N/A'}")
    if not messages or not isinstance(messages, list):
        return None

    latest_message = messages[-1]
    _dbg(f"last_msg_type: {type(latest_message).__name__}")
    _dbg(f"last_msg: {latest_message}")
    return latest_message


def _persist_trace(
    *,
    status: str,
    failed_steps: List[Dict[str, Any]],
    session_dir: str,
    session_id: str,
) -> tuple[List[Dict[str, Any]], Optional[str]]:
    """
    R2：任务终态确定后，固化本轮 Trace。

    1. 追加 kind=status 步骤（done / partial_success / error）
    2. build_trace_document 组装完整文档
    3. write_trace → output/session_*/trace.json
    4. task_store.set_trace 写入 steps + trace_path，供 GET /api/tasks 与前端面板

    Returns:
        (steps 列表, trace 文件绝对路径)
    """
    trace_event(kind="status", name=status, status=status)
    doc = build_trace_document(
        status=status,
        failed_steps=failed_steps,
        session_dir=session_dir,
    )
    path = write_trace(session_dir, doc)
    steps = list(doc.get("steps") or get_trace_steps())
    task_store.set_trace(session_id, steps=steps, trace_path=path)
    return steps, path


async def _consume_agent_stream(input_messages: dict[str, Any], config: dict[str, Any]) -> str | None:
    final_result: str | None = None
    agent = await get_main_agent()

    async for chunk in agent.astream(input_messages, config=config):
        _dbg(f"chunk: {chunk}")

        for node_name, state in chunk.items():
            last_msg = _extract_latest_message(node_name, state)
            if last_msg is None:
                continue

            if node_name == "model":
                tool_calls = getattr(last_msg, "tool_calls", None)
                content = getattr(last_msg, "content", None)

                if tool_calls:
                    for tool_call in tool_calls:
                        name = _tool_call_name(tool_call)
                        args = _tool_call_args(tool_call)
                        _dbg(f"tool_call_name: {name}", f"tool_call_args: {args}")
                        if name == "task":
                            # DeepAgents 委派子 Agent：记入 Trace + 推 WS 进度
                            assistant_name = args.get("subagent_type", "")
                            trace_event(
                                kind="assistant",
                                name=assistant_name or "subagent",
                                status="ok",
                                message=str(args.get("description", ""))[:200],
                            )
                            monitor.report_assistant(assistant_name, {"description": args.get("description", "")})
                        elif name:
                            monitor.report_tool(name, args)

                elif content:
                    final_result = content if isinstance(content, str) else str(content)
                    if _settings.runner_debug:
                        preview = final_result[:100]
                        print(f"主智能体执行结果，最终结果：{preview}")
                    # 模型正文 ≠ 任务终态；Trace 记 model_result，终态在 decide 之后
                    trace_event(
                        kind="model_result",
                        name="main_agent",
                        status="ok",
                        message=final_result[:200],
                    )
                    monitor.report_task_result(final_result)

            elif node_name == "tools":
                _dbg(
                    f"tool_result_name: {getattr(last_msg, 'name', None)}",
                    f"tool_result_content_preview: {str(getattr(last_msg, 'content', ''))[:200]}",
                )

    return final_result


async def run_deep_agent(task_query: str, session_id: str) -> None:
    _log("agent_start", task_query[:120], session_id=session_id)
    if _settings.runner_debug:
        print(f"当前会话的main_agent开始执行了！ 会话id:{session_id}")

    if not task_store.get(session_id):
        task_store.create(session_id, task_query)
    task_store.mark_running(session_id)

    _, session_dir_str, relative_dir, upload_prompt, _ = _prepare_session(session_id)
    task_store.set_session_dir(session_id, session_dir_str)

    tokens = setup_request_context(session_dir_str, session_id)
    failure_token = init_failure_steps()
    retry_token = init_retry_gate()
    # R2：与 failure 收集器成对初始化；finally 中 reset_trace
    trace_token = init_trace(thread_id=session_id, query=task_query)
    trace_event(kind="session", name="session_created", status="ok", message=session_dir_str)
    monitor.report_session_dir(session_dir_str)

    config = {"configurable": {"thread_id": session_id}}
    path_instruction = _build_path_instruction(relative_dir, upload_prompt)
    input_messages = {"messages": [{"role": "user", "content": task_query + path_instruction}]}

    _dbg(f"path_instruction: {path_instruction}")
    _dbg(f"input_messages: {input_messages}")

    try:
        final_result = await _consume_agent_stream(input_messages, config)
        result_text = final_result if final_result is not None else ""
        failed_steps = get_failure_steps()
        if failed_steps:
            monitor.report_failures_summary(failed_steps)

        status = decide_task_status(failed_steps)
        steps, trace_path = _persist_trace(
            status=status,
            failed_steps=failed_steps,
            session_dir=session_dir_str,
            session_id=session_id,
        )

        if status == "error":
            err_msg = "; ".join(
                f"{s.get('tool')}: {s.get('message')}" for s in failed_steps if s.get("role") == "critical"
            ) or "critical tool failed"
            short = f"关键步骤失败（{sum(1 for s in failed_steps if s.get('role') == 'critical')} 项），任务终止"
            task_store.mark_error(
                session_id,
                err_msg,
                failed_steps=failed_steps,
                steps=steps,
                trace_path=trace_path,
                session_dir=session_dir_str,
            )
            monitor.report_error(short, failed_steps=failed_steps)
            _log("agent_error_critical_tools", err_msg, session_id=session_id)
        elif status == "partial_success":
            task_store.mark_partial_success(
                session_id,
                result_text,
                failed_steps=failed_steps,
                session_dir=session_dir_str,
                steps=steps,
                trace_path=trace_path,
            )
            monitor.report_degraded(failed_steps, status="partial_success")
            _log("agent_partial_success", session_id=session_id, failed=len(failed_steps))
        else:
            task_store.mark_done(
                session_id,
                result_text,
                session_dir_str,
                steps=steps,
                trace_path=trace_path,
            )
            _log("agent_done", session_id=session_id)

    except asyncio.CancelledError:
        # R3：超时 wait_for 取消或客户端 cancel；finally 仍会 reset ContextVar
        failed_steps = get_failure_steps()
        cur = task_store.get(session_id) or {}
        st = cur.get("status") or "cancelled"
        if st in ("pending", "running"):
            st = "cancelled"
            try:
                steps, trace_path = _persist_trace(
                    status=st,
                    failed_steps=failed_steps,
                    session_dir=session_dir_str,
                    session_id=session_id,
                )
            except Exception:
                steps, trace_path = get_trace_steps(), None
            task_store.mark_cancelled(
                session_id,
                error="任务已取消",
                failed_steps=failed_steps or None,
                steps=steps,
                trace_path=trace_path,
                session_dir=session_dir_str,
            )
            monitor.report_cancelled("任务已取消")
        else:
            # 外层可能已 mark_timeout；仍尽量落盘 Trace
            try:
                _persist_trace(
                    status=st if st in ("timeout", "cancelled") else "cancelled",
                    failed_steps=failed_steps,
                    session_dir=session_dir_str,
                    session_id=session_id,
                )
            except Exception:
                pass
        _log("agent_cancelled", session_id=session_id, status=st)
        raise
    except Exception as e:
        log_error(_logger, "agent_error", str(e), session_id=session_id)
        failed_steps = get_failure_steps()
        try:
            steps, trace_path = _persist_trace(
                status="error",
                failed_steps=failed_steps,
                session_dir=session_dir_str,
                session_id=session_id,
            )
        except Exception:
            steps, trace_path = get_trace_steps(), None
        task_store.mark_error(
            session_id,
            str(e),
            failed_steps=failed_steps or None,
            steps=steps,
            trace_path=trace_path,
            session_dir=session_dir_str,
        )
        monitor.report_error(f"执行主 Agent 异常: {e}", failed_steps=failed_steps)
        raise
    finally:
        reset_trace(trace_token)
        reset_retry_gate(retry_token)
        reset_failure_steps(failure_token)
        reset_all_tokens(tokens)
        if _settings.runner_debug:
            print(f"[Runner] 结束 session_id={session_id}")
