"""
prompt/test_loader.py — config / context / prompt 三层自检脚本

验证基建模块能否正常加载，不依赖数据库和 LLM。
运行：python prompt/test_loader.py（已内置 sys.path 修复）
"""

import sys
from pathlib import Path

# 将项目根目录加入 Python 搜索路径
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.settings import get_settings
from context.session import (
    get_session_context,
    get_thread_context,
    get_trace_id,
    reset_all_tokens,
    setup_request_context,
)
from prompt.loader import SUB_AGENT_KEYS, get_main_agent_prompt, get_sub_agents_prompt, load_prompts


def test_settings():
    """验证 .env 能否被 Settings 正确读取。"""
    s = get_settings()
    assert s.mysql_database == "xiaoneng_db"
    assert s.openai_model
    print(f"[OK] settings: model={s.openai_model}, db={s.mysql_database}")


def test_context_isolation():
    """验证 ContextVar set/get/reset 是否正常。"""
    tokens_a = setup_request_context("/tmp/session_a", "thread-a")
    assert get_session_context() == "/tmp/session_a"
    assert get_thread_context() == "thread-a"
    assert get_trace_id()
    reset_all_tokens(tokens_a)
    assert get_session_context() is None
    print("[OK] context: set/get/reset")


def test_prompts():
    """验证 prompts.yml 结构及 5 个子 Agent 是否齐全。"""
    content = load_prompts()
    main = get_main_agent_prompt()
    subs = get_sub_agents_prompt()
    assert "效能负责人" in main["system_prompt"]
    assert len(SUB_AGENT_KEYS) == 5
    for key in SUB_AGENT_KEYS:
        assert key in subs
        assert subs[key]["name"]
    print(f"[OK] prompts: version={content['_meta']['version']}, sub_agents={list(subs.keys())}")


if __name__ == "__main__":
    test_settings()
    test_context_isolation()
    test_prompts()
    print("\n全部通过。")
