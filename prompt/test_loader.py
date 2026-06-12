"""快速验证 config / context / prompt 模块是否正常。"""
import sys
from pathlib import Path
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
    s = get_settings()
    assert s.mysql_database == "xiaoneng_db"
    assert s.openai_model
    print(f"[OK] settings: model={s.openai_model}, db={s.mysql_database}")


def test_context_isolation():
    tokens_a = setup_request_context("/tmp/session_a", "thread-a")
    assert get_session_context() == "/tmp/session_a"
    assert get_thread_context() == "thread-a"
    assert get_trace_id()
    reset_all_tokens(tokens_a)
    assert get_session_context() is None
    print("[OK] context: set/get/reset")


def test_prompts():
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
