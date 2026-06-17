"""
EfficiencyAgent 主 Agent：效能负责人。

- 组装 create_deep_agent + 5 个子 Agent
- run_deep_agent：会话目录、ContextVar、astream 进度推送
"""

import shutil
from pathlib import Path

from deepagents.graph import create_deep_agent
from langgraph.checkpoint.memory import InMemorySaver

from agent.subagent import ALL_SUBAGENTS
from api.monitor import monitor
from config.settings import get_settings
from context.session import reset_all_tokens, setup_request_context
from llm.model import model
from prompt.loader import get_main_agent_prompt
from tools.upload_file_read_tool import read_file_content

_main_cfg = get_main_agent_prompt()
_settings = get_settings()
_project_root = _settings.project_root

main_agent = create_deep_agent(
    model=model,
    system_prompt=_main_cfg["system_prompt"],
    tools=[read_file_content],
    checkpointer=InMemorySaver(),
    subagents=ALL_SUBAGENTS,
)


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


async def run_deep_agent(task_query: str, session_id: str) -> None:
    """
    异步执行主 Agent。

    Args:
        task_query: 用户自然语言任务
        session_id: 会话 / thread_id，用于 checkpoint 与目录隔离
    """
    print(f"task_query: {task_query}")
    print(f"session_id: {session_id}")

    session_dir, session_dir_str, relative_dir, upload_prompt, uploaded_files = _prepare_session(session_id)
    print(f"session_dir: {session_dir}")
    print(f"session_dir_str: {session_dir_str}")
    print(f"relative_dir: {relative_dir}")
    print(f"upload_prompt: {upload_prompt!r}")
    print(f"uploaded_files: {uploaded_files}")

    tokens = setup_request_context(session_dir_str, session_id)
    print(f"tokens: {tokens}")

    monitor.report_session_dir(session_dir_str)

    config = {"configurable": {"thread_id": session_id}}
    print(f"config: {config}")

    path_instruction = _build_path_instruction(relative_dir, upload_prompt)
    print(f"path_instruction: {path_instruction}")

    user_content = task_query + path_instruction
    print(f"user_content: {user_content}")

    input_messages = {"messages": [{"role": "user", "content": user_content}]}
    print(f"input_messages: {input_messages}")

    try:
        async for chunk in main_agent.astream(input_messages, config=config):
            print(f"chunk: {chunk}")
            for node_name, state in chunk.items():
                print(f"node_name: {node_name}")
                print(f"state: {state}")
                if not state or "messages" not in state:
                    continue
                messages = state["messages"]
                print(f"messages_count: {len(messages) if isinstance(messages, list) else 'N/A'}")
                if messages and isinstance(messages, list):
                    last_msg = messages[-1]
                    print(f"last_msg_type: {type(last_msg).__name__}")
                    print(f"last_msg: {last_msg}")
                    if node_name == "model":
                        if last_msg.tool_calls:
                            print(f"tool_calls: {last_msg.tool_calls}")
                            for tool_call in last_msg.tool_calls:
                                name = (
                                    tool_call.get("name")
                                    if isinstance(tool_call, dict)
                                    else getattr(tool_call, "name", None)
                                )
                                args = (
                                    tool_call.get("args") or {}
                                    if isinstance(tool_call, dict)
                                    else getattr(tool_call, "args", None) or {}
                                )
                                print(f"tool_call_name: {name}")
                                print(f"tool_call_args: {args}")
                                if name == "task":
                                    monitor.report_assistant(
                                        args.get("subagent_type", ""),
                                        {"description": args.get("description", "")},
                                    )
                        elif last_msg.content:
                            content = last_msg.content
                            preview = content[:100] if isinstance(content, str) else str(content)[:100]
                            print(f"主智能体执行结果，最终结果：{preview}")
                            monitor.report_task_result(content)
                    elif node_name == "tools":
                        print(f"tool_result_name: {getattr(last_msg, 'name', None)}")
                        print(f"tool_result_content_preview: {str(getattr(last_msg, 'content', ''))[:200]}")

    except Exception as e:
        print(f"exception: {e!r}")
        monitor._emit("error", f"执行主 Agent 异常: {str(e)}")
        raise
    finally:
        print(f"reset_all_tokens: {tokens}")
        reset_all_tokens(tokens)
