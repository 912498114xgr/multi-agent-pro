"""临时测试脚本：验证 llm.py 能否正确访问模型 API"""
from dotenv import load_dotenv, find_dotenv
import os
from langchain.chat_models import init_chat_model

load_dotenv(find_dotenv())

print("BASE_URL:", os.getenv("OPENAI_BASE_URL"))
print("MODEL:", os.getenv("OPENAI_MODEL"))
key = os.getenv("OPENAI_API_KEY")
print("API_KEY:", (key[:10] + "...") if key else None)

model = init_chat_model(
    model=os.getenv("OPENAI_MODEL"),
    model_provider="openai",
)

print("正在调用模型...")
response = model.invoke("你好，你是什么模型？")
print("Response:", response.content)
