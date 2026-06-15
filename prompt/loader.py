"""
prompt/loader.py — Prompt 配置加载器

从 prompt/prompts.yml 读取主 Agent 和 5 个子 Agent 的 system_prompt。
与 deep_search_pro 的 agent/prompts.py 不同：
  - 无 import 时 print 副作用
  - 启动时校验 YAML 结构，缺字段立即报错
  - 附带 _meta 元数据（版本号、数据库名）

子 Agent key 与 prompts.yml 中 sub_agents 的键一一对应：
  db / tavily / ragflow / analyst / writer
"""

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

import yaml

from config.settings import get_settings

# prompts.yml 与本文件同目录
PROMPT_FILE = Path(__file__).parent / "prompts.yml"

# 效能 Agent 的 5 个子 Agent 注册键（顺序与 PROJECT.md 一致）
SUB_AGENT_KEYS: List[str] = ["db", "tavily", "ragflow", "analyst", "writer"]

# 校验时要求的必填字段
REQUIRED_MAIN_KEYS = {"system_prompt"}
REQUIRED_SUB_KEYS = {"name", "description", "system_prompt"}


def load_yaml(file_path: Path) -> Dict[str, Any]:
    """安全加载 YAML。safe_load 不会执行 YAML 中的嵌入代码。"""
    with open(file_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def validate_prompts(content: Dict[str, Any]) -> None:
    """
    校验 prompts.yml 结构完整性。
    在 load_prompts 时调用，确保子 Agent 配置齐全，避免运行时才发现缺 prompt。
    """
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
    """
    加载并缓存完整 prompt 配置。
    lru_cache：进程内只读一次文件，修改 yml 后需重启。
    """
    settings = get_settings()
    content = load_yaml(PROMPT_FILE)
    validate_prompts(content)
    # 附加元数据，便于日志和调试
    content["_meta"] = {
        "version": settings.prompt_version,
        "file": str(PROMPT_FILE),
        "database": settings.mysql_database,
    }
    return content


def get_main_agent_prompt() -> Dict[str, Any]:
    """返回主 Agent（效能负责人）配置，含 system_prompt 字段。"""
    return load_prompts()["main_agent"]


def get_sub_agents_prompt() -> Dict[str, Any]:
    """返回全部子 Agent 配置字典。"""
    return load_prompts()["sub_agents"]


def get_sub_agent_prompt(key: str) -> Dict[str, Any]:
    """按 key 获取单个子 Agent 配置，供 subagent/*.py 组装字典时使用。"""
    sub_agents = get_sub_agents_prompt()
    if key not in sub_agents:
        raise KeyError(f"未知子 Agent: {key}，可用: {list(sub_agents.keys())}")
    return sub_agents[key]
