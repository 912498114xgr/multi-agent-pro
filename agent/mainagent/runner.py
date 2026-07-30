"""
EfficiencyAgent 主 Agent：效能负责人。

- 组装 create_deep_agent + 5 个子 Agent
- run_deep_agent：会话目录、ContextVar、astream 进度推送
"""

import shutil
from pathlib import Path
from typing import Any

from deepagents.graph import create_deep_agent
from langgraph.checkpoint.memory import InMemorySaver

from agent.subagent import ALL_SUBAGENTS
from api.monitor import monitor
from api.task_store import task_store
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

main_agent = create_deep_agent(
    model=model,
    system_prompt=_main_cfg["system_prompt"],
    tools=[read_file_content],
    checkpointer=InMemorySaver(),
    subagents=ALL_SUBAGENTS,
)


def _dbg(*args: Any) -> None:
    if _settings.runner_debug:
        print(*args)


def _log(event: str, message: str = "", **extra: Any) -> None:
    """结构化日志仅 debug 模式写入，避免与 [Monitor:xxx] 控制台格式混杂。"""
    if _settings.runner_debug:
        from observability.logging import log_info
        log_info(_logger, event, message, **extra)


def _prepare_session(session_id: str) -> tuple[Path, str, str, str, list[str]]:
    """创建 output 目录，复制上传文件，返回路径信息。"""
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
    """LangGraph 每个 chunk 里有节点状态；我们只关心最新一条 message。"""
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


async def _consume_agent_stream(input_messages: dict[str, Any], config: dict[str, Any]) -> str | None:
    """
    流式执行主 Agent，并把关键分支转成 monitor 进度事件。

    读这段时抓住 3 个分支：
      1. model + tool_calls：模型准备调用子 Agent 或工具
      2. model + content：模型产出最终答案
      3. tools：工具返回结果，默认只在 debug 模式打印
    """
    final_result: str | None = None

    async for chunk in main_agent.astream(input_messages, config=config):
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
                        # 子agent
                        if name == "task":
                            monitor.report_assistant(
                                args.get("subagent_type", ""),
                                {"description": args.get("description", "")},
                            )
                        # 工具
                        elif name:
                            monitor.report_tool(name, args)

                elif content:
                    final_result = content if isinstance(content, str) else str(content)
                    preview = final_result[:100]
                    print(f"主智能体执行结果，最终结果：{preview}")
                    monitor.report_task_result(final_result)

            elif node_name == "tools":
                _dbg(
                    f"tool_result_name: {getattr(last_msg, 'name', None)}",
                    f"tool_result_content_preview: {str(getattr(last_msg, 'content', ''))[:200]}",
                )

    return final_result


async def run_deep_agent(task_query: str, session_id: str) -> None:
    """
    异步执行主 Agent。

    Args:
        task_query: 用户自然语言任务
        session_id: 会话 / thread_id，用于 checkpoint 与目录隔离
    """
    _log("agent_start", task_query[:120], session_id=session_id)
    print(f"当前会话的main_agent开始执行了！ 会话id:{session_id}")

    if not task_store.get(session_id):
        task_store.create(session_id, task_query)
    task_store.mark_running(session_id)

    _, session_dir_str, relative_dir, upload_prompt, _ = _prepare_session(session_id)
    task_store.set_session_dir(session_id, session_dir_str)

    tokens = setup_request_context(session_dir_str, session_id)
    monitor.report_session_dir(session_dir_str)

    config = {"configurable": {"thread_id": session_id}}
    path_instruction = _build_path_instruction(relative_dir, upload_prompt)
    input_messages = {"messages": [{"role": "user", "content": task_query + path_instruction}]}

    _dbg(f"path_instruction: {path_instruction}")
    _dbg(f"input_messages: {input_messages}")

    try:
        final_result = await _consume_agent_stream(input_messages, config)

        if final_result is not None:
            task_store.mark_done(session_id, final_result, session_dir_str)
            _log("agent_done", session_id=session_id)
        else:
            task_store.mark_done(session_id, "", session_dir_str)
            _log("agent_done_no_content", session_id=session_id)

    except Exception as e:
        log_error(_logger, "agent_error", str(e), session_id=session_id)
        task_store.mark_error(session_id, str(e))
        monitor._emit("error", f"执行主 Agent 异常: {str(e)}")
        raise
    finally:
        reset_all_tokens(tokens)
        print(f"[Runner] 结束 session_id={session_id}")
