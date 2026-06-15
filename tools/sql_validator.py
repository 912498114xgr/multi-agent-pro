"""
tools/sql_validator.py — SQL 安全校验（企业级只读约束）

在 execute_sql_query 执行前拦截危险语句，防止 LLM 生成 DELETE/DROP 等写操作。
注意：这是应用层防护，生产环境仍建议使用只读数据库账号。
"""

import re
from typing import Tuple

# 危险关键字黑名单（单词边界匹配，减少误伤）
_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|REPLACE|GRANT|REVOKE|EXEC|EXECUTE|CALL)\b",
    re.IGNORECASE,
)
# 允许开头的语句类型
_ALLOWED_START = re.compile(r"^\s*(SELECT|SHOW|DESCRIBE|DESC|EXPLAIN)\b", re.IGNORECASE)
# 表名只允许字母数字下划线，防 SQL 注入拼接
_TABLE_NAME = re.compile(r"^[a-zA-Z0-9_]+$")


def validate_readonly_sql(query: str) -> Tuple[bool, str]:
    """
    校验自定义 SQL 是否为安全的只读查询。

    Returns:
        (True, "") 表示通过；(False, "原因") 表示拒绝
    """
    if not query or not query.strip():
        return False, "SQL 语句不能为空"

    normalized = query.strip().rstrip(";")

    # 禁止多语句（; 分隔可执行 DROP;SELECT 等攻击）
    if ";" in normalized:
        return False, "不允许执行多条 SQL 语句"

    if not _ALLOWED_START.match(normalized):
        return False, "仅允许 SELECT / SHOW / DESCRIBE / EXPLAIN 语句"

    if _FORBIDDEN.search(normalized):
        return False, "检测到危险 SQL 关键字，已拒绝执行"

    return True, ""


def validate_table_name(table_name: str) -> Tuple[bool, str]:
    """
    校验 get_table_data 的表名参数，防止 `table; DROP TABLE` 类注入。
    """
    if not table_name or not _TABLE_NAME.match(table_name):
        return False, f"非法表名: {table_name}"
    return True, ""
