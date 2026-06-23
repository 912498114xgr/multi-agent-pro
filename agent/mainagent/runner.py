"""
EfficiencyAgent 主 Agent：效能负责人。

- 组装 create_deep_agent + 5 个子 Agent
- run_deep_agent：会话目录、ContextVar、astream 进度推送、Redis 断点续跑
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from deepagents.graph import create_deep_agent

from agent.checkpoint import get_checkpointer
from agent.subagent import ALL_SUBAGENTS
from api.monitor import monitor
from api.task_store import get_task_store
from config.settings import get_settings
from context.session import reset_all_tokens, setup_request_context
from llm.model import model
from observability.logging import get_logger, log_error
from prompt.loader import get_main_agent_prompt
from tools.upload_file_read_tool import read_file_content

_main_cfg = get_main_agent_prompt()
_settings = get_settings()
_project_root = _settings.project_root
_logger = get_logger("runner")

_main_agent = None


def get_main_agent():
    """懒加载主 Agent，checkpointer 随 REDIS_URL 切换 Redis / 内存。"""
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


def __getattr__(name: str):
    if name == "main_agent":
        return get_main_agent()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


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


def _extract_final_from_messages(messages: list) -> str | None:
    for msg in reversed(messages):
        tool_calls = getattr(msg, "tool_calls", None)
        if tool_calls:
            continue
        content = getattr(msg, "content", None)
        if content:
            return content if isinstance(content, str) else str(content)
    return None


def _extract_final_from_state(state: Any) -> str | None:
    if not state or not getattr(state, "values", None):
        return None
    messages = state.values.get("messages", [])
    if not isinstance(messages, list):
        return None
    return _extract_final_from_messages(messages)


async def _finalize_if_graph_complete(session_id: str, session_dir_str: str) -> bool:
    """checkpoint 已无待执行节点时补 mark_done（崩溃窗口修复）。"""
    agent = get_main_agent()
    config = {"configurable": {"thread_id": session_id}}
    state = await agent.aget_state(config)
    if not state or state.next:
        return False

    final_result = _extract_final_from_state(state)
    store = get_task_store()
    if final_result is not None:
        store.mark_done(session_id, final_result, session_dir_str)
        monitor.report_task_result(final_result)
    else:
        store.mark_done(session_id, "", session_dir_str)
    return True


async def _process_stream_chunk(chunk: dict, final_holder: list) -> None:
    for node_name, state in chunk.items():
        _dbg(f"node_name: {node_name}")
        _dbg(f"state: {state}")
        if not state or "messages" not in state:
            continue
        messages = state["messages"]
        if not messages or not isinstance(messages, list):
            continue
        last_msg = messages[-1]
        _dbg(f"last_msg_type: {type(last_msg).__name__}")
        _dbg(f"last_msg: {last_msg}")

        if node_name == "model":
            if last_msg.tool_calls:
                for tool_call in last_msg.tool_calls:
                    name = _tool_call_name(tool_call)
                    args = _tool_call_args(tool_call)
                    _dbg(f"tool_call_name: {name}", f"tool_call_args: {args}")
                    if name == "task":
                        monitor.report_assistant(
                            args.get("subagent_type", ""),
                            {"description": args.get("description", "")},
                        )
                    elif name:
                        monitor.report_tool(name, args)
            elif last_msg.content:
                content = last_msg.content
                final_result = content if isinstance(content, str) else str(content)
                final_holder.append(final_result)
                preview = final_result[:100]
                print(f"主智能体执行结果，最终结果：{preview}")
                monitor.report_task_result(final_result)
        elif node_name == "tools":
            tool_name = getattr(last_msg, "name", None)
            if tool_name == "task":
                monitor.report_assistant_done()
            _dbg(
                f"tool_result_name: {tool_name}",
                f"tool_result_content_preview: {str(getattr(last_msg, 'content', ''))[:200]}",
            )


async def run_deep_agent(task_query: str, session_id: str, *, resume: bool = False) -> None:
    """
    异步执行主 Agent。

    Args:
        task_query: 用户自然语言任务
        session_id: 会话 / thread_id，用于 checkpoint 与目录隔离
        resume: True 时从 Redis checkpoint 续跑，不注入新用户消息
    """
    store = get_task_store()
    agent = get_main_agent()
    config = {"configurable": {"thread_id": session_id}}

    _log("agent_start", task_query[:120], session_id=session_id, resume=resume)
    print(f"当前会话的main_agent开始执行了！ 会话id:{session_id} resume={resume}")

    _, session_dir_str, relative_dir, upload_prompt, _ = _prepare_session(session_id)
    stream_input: dict | None

    if resume:
        existing = store.get(session_id)
        if not existing:
            print(f"[Recovery] 跳过 {session_id}：任务记录不存在")
            return
        if existing.get("session_dir"):
            session_dir_str = existing["session_dir"]
        state = await agent.aget_state(config)
        if not state or not state.next:
            if await _finalize_if_graph_complete(session_id, session_dir_str):
                print(f"[Recovery] {session_id} checkpoint 已完成，已补记 done")
            else:
                store.mark_error(session_id, "无可恢复的 checkpoint")
            return
        store.mark_running(session_id)
        stream_input = None
        task_query = existing.get("query") or task_query
    else:
        if not store.get(session_id):
            store.create(session_id, task_query)
        store.mark_running(session_id)
        store.set_session_dir(session_id, session_dir_str)

        path_instruction = _build_path_instruction(relative_dir, upload_prompt)
        stream_input = {
            "messages": [{"role": "user", "content": task_query + path_instruction}]
        }
        _dbg(f"path_instruction: {path_instruction}")
        _dbg(f"input_messages: {stream_input}")

    tokens = setup_request_context(session_dir_str, session_id)
    if not resume:
        monitor.report_session_dir(session_dir_str)

    final_holder: list[str] = []

    try:
        async for chunk in agent.astream(stream_input, config=config):
            _dbg(f"chunk: {chunk}")
            await _process_stream_chunk(chunk, final_holder)

        final_result = final_holder[0] if final_holder else None
        if final_result is not None:
            store.mark_done(session_id, final_result, session_dir_str)
            _log("agent_done", session_id=session_id)
        elif await _finalize_if_graph_complete(session_id, session_dir_str):
            _log("agent_done_recovered", session_id=session_id)
        else:
            store.mark_done(session_id, "", session_dir_str)
            _log("agent_done_no_content", session_id=session_id)

    except Exception as e:
        log_error(_logger, "agent_error", str(e), session_id=session_id)
        store.mark_error(session_id, str(e))
        monitor._emit("error", f"执行主 Agent 异常: {str(e)}")
        raise
    finally:
        reset_all_tokens(tokens)
        print(f"[Runner] 结束 session_id={session_id}")


async def recover_interrupted_tasks() -> None:
    """启动时扫描 running 任务，从 Redis checkpoint 自动续跑。"""
    if not _settings.use_redis_task_store:
        return

    import asyncio

    store = get_task_store()
    running = store.list_running()
    if not running:
        return

    for task in running:
        thread_id = task["thread_id"]
        query = task.get("query") or ""
        print(f"[Recovery] scheduling resume thread_id={thread_id}")
        asyncio.create_task(run_deep_agent(query, thread_id, resume=True))
