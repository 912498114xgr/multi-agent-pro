from prompt.loader import get_sub_agent_prompt
from tools.ragflow_tools import create_ask_delete, get_assistant_list

_cfg = get_sub_agent_prompt("ragflow")

knowledge_agent = {
    "name": _cfg["name"],
    "description": _cfg["description"],
    "system_prompt": _cfg["system_prompt"],
    "tools": [get_assistant_list, create_ask_delete],
}
