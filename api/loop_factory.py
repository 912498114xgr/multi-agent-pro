"""
Windows 下 uvicorn 0.41+ 默认 loop_factory 会强制 ProactorEventLoop，
与 psycopg 异步（AsyncPostgresSaver）不兼容。此处提供 Selector 工厂。

uvicorn / run_api 通过 --loop api.loop_factory:selector_loop 使用。
"""

from __future__ import annotations

import asyncio
import selectors
import sys


def selector_loop() -> asyncio.AbstractEventLoop:
    """供 uvicorn Config.loop 使用：Callable[[], AbstractEventLoop]。"""
    if sys.platform == "win32":
        return asyncio.SelectorEventLoop(selectors.SelectSelector())
    return asyncio.new_event_loop()
