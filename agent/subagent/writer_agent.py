from prompt.loader import get_sub_agent_prompt
from tools.markdown_tools import generate_markdown
from tools.pdf_tools import convert_md_to_pdf

_cfg = get_sub_agent_prompt("writer")

writer_agent = {
    "name": _cfg["name"],
    "description": _cfg["description"],
    "system_prompt": _cfg["system_prompt"],
    "tools": [generate_markdown, convert_md_to_pdf],
}
