"""
结构化日志：自动附带 trace_id / thread_id。
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any, Optional

from context.session import get_thread_context, get_trace_id

_CONFIGURED = False


def _configure_root() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    root = logging.getLogger("efficiency_agent")
    root.setLevel(logging.INFO)
    root.handlers.clear()
    root.addHandler(handler)
    root.propagate = False
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    _configure_root()
    return logging.getLogger(f"efficiency_agent.{name}")


def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    message: str = "",
    **extra: Any,
) -> None:
    payload = {
        "event": event,
        "message": message,
        "trace_id": get_trace_id(),
        "thread_id": get_thread_context(),
        **extra,
    }
    logger.log(level, json.dumps(payload, ensure_ascii=False, default=str))


def log_info(logger: logging.Logger, event: str, message: str = "", **extra: Any) -> None:
    log_event(logger, logging.INFO, event, message, **extra)


def log_error(logger: logging.Logger, event: str, message: str = "", **extra: Any) -> None:
    log_event(logger, logging.ERROR, event, message, **extra)
