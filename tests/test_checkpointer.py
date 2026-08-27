"""R6b: checkpointer factory."""

from __future__ import annotations

import asyncio
import os
import unittest

from agent.checkpointer import (
    close_checkpointer,
    get_checkpointer,
    init_checkpointer,
    reset_checkpointer_for_tests,
)


class CheckpointerFactoryTests(unittest.TestCase):
    def tearDown(self) -> None:
        asyncio.run(close_checkpointer())
        reset_checkpointer_for_tests()
        os.environ.pop("CHECKPOINTER_BACKEND", None)
        os.environ.pop("AGENT_DATABASE_URL", None)
        from config.settings import get_settings

        get_settings.cache_clear()
        from agent.mainagent.runner import reset_main_agent_for_tests

        reset_main_agent_for_tests()

    def test_memory_backend(self) -> None:
        os.environ["CHECKPOINTER_BACKEND"] = "memory"
        from config.settings import get_settings

        get_settings.cache_clear()
        reset_checkpointer_for_tests()
        asyncio.run(init_checkpointer())
        cp = get_checkpointer()
        from langgraph.checkpoint.memory import InMemorySaver

        self.assertIsInstance(cp, InMemorySaver)


if __name__ == "__main__":
    unittest.main()
