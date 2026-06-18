"""临时测试脚本：验证 LLM 能否正确访问模型 API（与 llm/model.py 同一路径）"""
import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
_script_dir = str(Path(__file__).resolve().parent)
# 避免 llm/ 目录下的 llm.py 抢占包名
sys.path = [str(_root)] + [p for p in sys.path if p not in (str(_root), _script_dir, "")]

from config.settings import get_settings
from llm.model import get_model

settings = get_settings()

print("BASE_URL:", settings.openai_base_url)
print("MODEL:", settings.openai_model)
key = settings.openai_api_key
print("API_KEY:", (key[:10] + "...") if key else None)

if not settings.openai_api_key:
    raise SystemExit("错误：OPENAI_API_KEY 未配置")

model = get_model()

print("正在调用模型...")
response = model.invoke("你好，你是什么模型？请用一句话回答。")
print("Response:", response.content)
if response.response_metadata:
    print("model_name:", response.response_metadata.get("model_name"))
