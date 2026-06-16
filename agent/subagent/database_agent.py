from prompt.loader import get_sub_agent_prompt
from tools.db_tools import execute_sql_query, get_table_data, list_sql_tables

_cfg = get_sub_agent_prompt("db")

database_agent = {
    "name": _cfg["name"],
    "description": _cfg["description"],
    "system_prompt": _cfg["system_prompt"],
    "tools": [list_sql_tables, get_table_data, execute_sql_query],
}
