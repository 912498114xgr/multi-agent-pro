from prompt.loader import get_sub_agent_prompt
from tools.tavily_tool import internet_search

_cfg = get_sub_agent_prompt("tavily")

search_agent = {
    "name": _cfg["name"],
    "description": _cfg["description"],
    "system_prompt": _cfg["system_prompt"],
    "tools": [internet_search],
}
