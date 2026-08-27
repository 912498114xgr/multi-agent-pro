"""
API 启动入口。Windows + Postgres checkpointer 必须用本脚本（或指定 --loop），
因为 uvicorn 0.41 在 Win 上默认强制 ProactorEventLoop，psycopg 异步会启动失败。

用法：
  python run_api.py
  python run_api.py --port 8000
  python run_api.py --reload
"""

from __future__ import annotations

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description="Start EfficiencyAgent API")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true", help="热重载")
    args = parser.parse_args()

    import uvicorn

    # 显式 Selector：覆盖 uvicorn 在 Windows 上默认的 ProactorEventLoop
    uvicorn.run(
        "api.server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        loop="api.loop_factory:selector_loop",
    )


if __name__ == "__main__":
    main()
