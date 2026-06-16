from prompt.loader import get_sub_agent_prompt

_cfg = get_sub_agent_prompt("analyst")

analyst_agent = {
    "name": _cfg["name"],
    "description": _cfg["description"],
    "system_prompt": _cfg["system_prompt"],
    "tools": [],
}
