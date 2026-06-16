"""兼容旧导入：from llm.llm import model"""

from llm.model import get_model, model

__all__ = ["model", "get_model"]
