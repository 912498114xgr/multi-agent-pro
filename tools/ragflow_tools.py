"""
tools/ragflow_tools.py — 内部知识库工具（规范知识子 Agent 绑定）

未接入或异常为 optional 失败，主流程可降级。
"""

from langchain_core.tools import tool

from config.settings import get_settings
from tools.tool_result import begin_tool, format_tool_error, format_tool_ok


@tool
def get_assistant_list() -> str:
    """
    列出 RAGFlow 服务中可用的知识库助手及其关联数据集。
    规范知识子 Agent 的第一步：先知道有哪些助手可以提问。
    """
    blocked = begin_tool("get_assistant_list")
    if blocked:
        return blocked
    settings = get_settings()
    if not settings.ragflow_api_url or not settings.ragflow_api_key:
        return format_tool_error(
            tool="get_assistant_list",
            message="提示：RAGFlow 尚未接入（.env 中 RAGFLOW_API_URL / RAGFLOW_API_KEY 为空）。MVP 阶段请使用其他助手。",
            error_type="config_missing",
        )

    try:
        from ragflow_sdk import RAGFlow
        client = RAGFlow(api_key=settings.ragflow_api_key, base_url=settings.ragflow_api_url)
        chat_list = client.list_chats()
        if not chat_list:
            return format_tool_ok(tool="get_assistant_list", body="没有任何可用助手")
        lines = []
        for chat in chat_list:
            datasets = [d["name"] for d in (chat.datasets or []) if isinstance(d, dict)]
            lines.append(f"助手:{chat.name}; 描述:{chat.description}; 知识库:{'、'.join(datasets)}")
        return format_tool_ok(tool="get_assistant_list", body="\n".join(lines))
    except ImportError:
        return format_tool_error(
            tool="get_assistant_list",
            message="错误：未安装 ragflow_sdk",
            error_type="dependency",
        )
    except Exception as e:
        return format_tool_error(
            tool="get_assistant_list",
            message=f"查询助手异常：{e}",
            error_type="upstream",
            retryable=True,
        )


@tool
def create_ask_delete(chat_name: str, question: str) -> str:
    """
    向指定 RAGFlow 助手提问，单次会话模式（问完即删 session，不污染历史）。

    Args:
        chat_name: 助手名称，须与 get_assistant_list 返回的一致
        question: 向知识库提问的内容
    """
    blocked = begin_tool("create_ask_delete", {"chat_name": chat_name, "question": question})
    if blocked:
        return blocked
    settings = get_settings()
    if not settings.ragflow_api_url or not settings.ragflow_api_key:
        return format_tool_error(
            tool="create_ask_delete",
            message="提示：RAGFlow 尚未接入，无法查询内部规范。",
            error_type="config_missing",
        )

    try:
        from ragflow_sdk import RAGFlow
        client = RAGFlow(api_key=settings.ragflow_api_key, base_url=settings.ragflow_api_url)
        chats = client.list_chats(name=chat_name)
        use_chat = chats[0]
        session = use_chat.create_session(name="temp_ask")
        response = session.ask(question=question, stream=True)
        result = ""
        for part in response:
            result = part.content
        use_chat.delete_sessions(ids=[session.id])
        return format_tool_ok(tool="create_ask_delete", body=result)
    except ImportError:
        return format_tool_error(
            tool="create_ask_delete",
            message="错误：未安装 ragflow_sdk",
            error_type="dependency",
        )
    except Exception as e:
        return format_tool_error(
            tool="create_ask_delete",
            message=f"提问失败：{e}",
            error_type="upstream",
            retryable=True,
        )
