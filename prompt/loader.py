from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

import yaml

from config.settings import get_settings

PROMPT_FILE = Path(__file__).parent / "prompts.yml"

# 子 Agent 注册顺序（与 main_agent 委派名称一致）
SUB_AGENT_KEYS: List[str] = ["db", "tavily", "ragflow", "analyst", "writer"]

REQUIRED_MAIN_KEYS = {"system_prompt"}
REQUIRED_SUB_KEYS = {"name", "description", "system_prompt"}


def load_yaml(file_path: Path) -> Dict[str, Any]:
    with open(file_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def validate_prompts(content: Dict[str, Any]) -> None:
    """校验 prompts.yml 结构，启动时发现配置错误。"""
    if "main_agent" not in content:
        raise ValueError("prompts.yml 缺少 main_agent 节点")
    if "sub_agents" not in content:
        raise ValueError("prompts.yml 缺少 sub_agents 节点")

    main = content["main_agent"]
    missing_main = REQUIRED_MAIN_KEYS - set(main.keys())
    if missing_main:
        raise ValueError(f"main_agent 缺少字段: {missing_main}")

    sub_agents = content["sub_agents"]
    for key in SUB_AGENT_KEYS:
        if key not in sub_agents:
            raise ValueError(f"sub_agents 缺少子 Agent 配置: {key}")
        missing_sub = REQUIRED_SUB_KEYS - set(sub_agents[key].keys())
        if missing_sub:
            raise ValueError(f"sub_agents.{key} 缺少字段: {missing_sub}")


@lru_cache
def load_prompts() -> Dict[str, Any]:
    settings = get_settings()
    content = load_yaml(PROMPT_FILE)
    validate_prompts(content)
    content["_meta"] = {
        "version": settings.prompt_version,
        "file": str(PROMPT_FILE),
        "database": settings.mysql_database,
    }
    return content


def get_main_agent_prompt() -> Dict[str, Any]:
    return load_prompts()["main_agent"]


def get_sub_agents_prompt() -> Dict[str, Any]:
    return load_prompts()["sub_agents"]


def get_sub_agent_prompt(key: str) -> Dict[str, Any]:
    sub_agents = get_sub_agents_prompt()
    if key not in sub_agents:
        raise KeyError(f"未知子 Agent: {key}，可用: {list(sub_agents.keys())}")
    return sub_agents[key]
