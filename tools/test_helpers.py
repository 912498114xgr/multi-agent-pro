"""
tools/test_helpers.py — 工具单独测试时的 ContextVar 辅助

单独运行 tools/run_tests.py 时没有 FastAPI 请求链路，
需要手动 setup_request_context 模拟 session_dir，工具才能正确读写文件。

测试目录固定为：tools/test_data/session_test/
"""

import sys
from pathlib import Path

# 把项目根加入 sys.path，解决「No module named config」问题
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def get_test_session_dir() -> Path:
    """返回并创建工具测试用的固定 session 目录。"""
    d = PROJECT_ROOT / "tools" / "test_data" / "session_test"
    d.mkdir(parents=True, exist_ok=True)
    return d


def setup_test_context():
    """
    模拟一次请求的 ContextVar 环境。
    返回 tokens，测试结束必须 teardown_test_context(tokens)。
    """
    from context.session import setup_request_context
    session_dir = str(get_test_session_dir().resolve())
    return setup_request_context(session_dir=session_dir, thread_id="test-thread-001")


def teardown_test_context(tokens) -> None:
    """清理 ContextVar，防止影响同进程后续测试。"""
    from context.session import reset_all_tokens
    reset_all_tokens(tokens)
