"""
tools/tavily_tool.py — 公网搜索工具（行业检索子 Agent 绑定）

通过 Tavily API 检索研发效能方法论、DORA 指标、行业 benchmark 等公开信息。
不用于查询 xiaoneng_db 或 RAGFlow 内部知识库。
"""

import time
from typing import Literal

from langchain_core.tools import tool
from tavily import TavilyClient

from config.settings import get_settings
from tools.hooks import hooks


@tool
def internet_search(
    query: str,
    topic: Literal["news", "finance", "general"] = "general",
    max_results: int = 5,
    include_raw_content: bool = False,
) -> str:
    """
    根据问题检索公网信息。

    Args:
        query: 搜索关键词，如「研发效能 DORA 指标 2025」
        topic: 搜索类别，general 最常用
        max_results: 返回条数上限，默认 5 控制 token
        include_raw_content: 是否返回网页原文（更耗 token）
    """
    hooks.report_tool("internet_search", {
        "query": query, "topic": topic, "max_results": max_results,
    })
    settings = get_settings()
    if not settings.tavily_api_key:
        return "错误：TAVILY_API_KEY 未配置"

    start = time.perf_counter()
    try:
        client = TavilyClient(api_key=settings.tavily_api_key)
        result = client.search(
            query=query,
            topic=topic,
            max_results=max_results,
            include_raw_content=include_raw_content,
        )
        print(f"[Tavily] ms={(time.perf_counter()-start)*1000:.0f} query={query[:80]}")
        return str(result)
    except Exception as e:
        return f"网络搜索失败：{str(e)}"
