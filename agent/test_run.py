"""
命令行试跑主 Agent。

用法（项目根目录）:
  python agent/test_run.py
  python agent/test_run.py "查 Sprint-12 有哪些开放缺陷"
"""

import asyncio
import sys
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    import deepagents  # noqa: F401
except ModuleNotFoundError:
    print("=" * 60)
    print("错误: 未找到 deepagents 模块")
    print(f"当前 Python: {sys.executable}")
    print(f"请使用项目虚拟环境: {VENV_PYTHON}")
    print("\nPyCharm: Settings → Project → Python Interpreter")
    print("  选择 Existing → multi-agent-pro\\.venv\\Scripts\\python.exe")
    print("\n或命令行运行:")
    print(r"  .\.venv\Scripts\python.exe agent\test_run.py")
    print("=" * 60)
    sys.exit(1)

from agent.mainagent.runner import run_deep_agent


async def main() -> None:
    query = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "请查询 xiaoneng_db 中 Sprint-12 迭代有哪些开放缺陷，并简要总结。"
    )
    session_id = f"cli-{uuid.uuid4().hex[:8]}"
    print(f"Query: {query}\nSession: {session_id}\n")
    await run_deep_agent(query, session_id)


if __name__ == "__main__":
    asyncio.run(main())
