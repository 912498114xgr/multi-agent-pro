"""
tools/ragflow_tools.py — 内部知识库工具（规范知识子 Agent 绑定）

查询 RAGFlow 中的研发规范、发布流程、代码评审标准等内部文档。

MVP 策略：
  .env 未配置 RAGFLOW_API_URL / RAGFLOW_API_KEY 时，
  返回友好提示而非抛异常，主 Agent 可改用其他数据源完成任务。
"""

from langchain_core.tools import tool

from config.settings import get_settings
from tools.hooks import hooks


@tool
def get_assistant_list() -> str:
    """
    列出 RAGFlow 服务中可用的知识库助手及其关联数据集。
    规范知识子 Agent 的第一步：先知道有哪些助手可以提问。
    """
    hooks.report_tool("get_assistant_list")
    settings = get_settings()
    if not settings.ragflow_api_url or not settings.ragflow_api_key:
        return "提示：RAGFlow 尚未接入（.env 中 RAGFLOW_API_URL / RAGFLOW_API_KEY 为空）。MVP 阶段请使用其他助手。"

    try:
        from ragflow_sdk import RAGFlow
        client = RAGFlow(api_key=settings.ragflow_api_key, base_url=settings.ragflow_api_url)
        chat_list = client.list_chats()
        if not chat_list:
            return "没有任何可用助手"
        lines = []
        for chat in chat_list:
            datasets = [d["name"] for d in (chat.datasets or []) if isinstance(d, dict)]
            lines.append(f"助手:{chat.name}; 描述:{chat.description}; 知识库:{'、'.join(datasets)}")
        return "\n".join(lines)
    except ImportError:
        return "错误：未安装 ragflow_sdk"
    except Exception as e:
        return f"查询助手异常：{str(e)}"


@tool
def create_ask_delete(chat_name: str, question: str) -> str:
    """
    向指定 RAGFlow 助手提问，单次会话模式（问完即删 session，不污染历史）。

    Args:
        chat_name: 助手名称，须与 get_assistant_list 返回的一致
        question: 向知识库提问的内容
    """
    hooks.report_tool("create_ask_delete", {"chat_name": chat_name, "question": question})
    settings = get_settings()
    if not settings.ragflow_api_url or not settings.ragflow_api_key:
        return "提示：RAGFlow 尚未接入，无法查询内部规范。"

    try:
        from ragflow_sdk import RAGFlow
        client = RAGFlow(api_key=settings.ragflow_api_key, base_url=settings.ragflow_api_url)
        chats = client.list_chats(name=chat_name)
        use_chat = chats[0]
        session = use_chat.create_session(name="temp_ask")
        response = session.ask(question=question, stream=True)
        result = ""
        for part in response:
            result = part.content  # 流式取最后一段完整内容
        use_chat.delete_sessions(ids=[session.id])
        return result
    except ImportError:
        return "错误：未安装 ragflow_sdk"
    except Exception as e:
        return f"提问失败：{str(e)}"
