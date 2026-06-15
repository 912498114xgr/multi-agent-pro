"""
prompt 包 — Prompt 配置加载。

YAML 源文件：prompt/prompts.yml
加载器：prompt/loader.py
"""

from prompt.loader import (
    SUB_AGENT_KEYS,
    get_main_agent_prompt,
    get_sub_agent_prompt,
    get_sub_agents_prompt,
    load_prompts,
)

__all__ = [
    "load_prompts",
    "get_main_agent_prompt",
    "get_sub_agents_prompt",
    "get_sub_agent_prompt",
    "SUB_AGENT_KEYS",
]
