"""验证 5 个子 Agent 配置是否正确加载。"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.subagent import ALL_SUBAGENTS


def main() -> None:
    print(f"子 Agent 数量: {len(ALL_SUBAGENTS)}")
    for agent in ALL_SUBAGENTS:
        tools = [t.name for t in agent["tools"]]
        print(f"  - {agent['name']:12} tools={tools or '(无，纯分析)'}")
    print("\n全部加载成功。")


if __name__ == "__main__":
    main()
