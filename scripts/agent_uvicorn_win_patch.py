"""
Windows：把 uvicorn 默认的 ProactorEventLoop 换成 Selector，
否则 `uvicorn api.server:app` 启动时 AsyncPostgresSaver / psycopg 会失败。

由 site-packages 下的 .pth 在解释器启动时自动 import。
"""

from __future__ import annotations

import sys


def _patch_uvicorn_loop() -> None:
    if sys.platform != "win32":
        return
    try:
        import asyncio
        import selectors

        import uvicorn.loops.asyncio as uvicorn_asyncio

        def asyncio_loop_factory(use_subprocess: bool = False):
            def factory() -> asyncio.AbstractEventLoop:
                return asyncio.SelectorEventLoop(selectors.SelectSelector())

            return factory

        uvicorn_asyncio.asyncio_loop_factory = asyncio_loop_factory
    except Exception:
        # uvicorn 未安装时忽略
        pass


_patch_uvicorn_loop()
