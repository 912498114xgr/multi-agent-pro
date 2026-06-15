"""
tools/db_tools.py — 数据库查询工具（数据查询子 Agent 绑定）

连接 xiaoneng_db，提供三个 LangChain Tool：
  list_sql_tables    — 列出所有表
  get_table_data     — 预览单表前 100 行
  execute_sql_query  — 执行自定义只读 SQL

企业级特性：
  - 配置来自 config.settings，不直接 os.getenv
  - execute_sql_query 经 sql_validator 只读校验
  - get_table_data 表名白名单校验
  - 每次查询打印 SQL 审计日志（耗时、结果大小）
  - 异常返回字符串而非抛错，避免打断 Agent 流程
"""

import time

from langchain_core.tools import tool
from mysql.connector import Error, connect

from config.settings import get_settings
from tools.hooks import hooks
from tools.sql_validator import validate_readonly_sql, validate_table_name


def _rows_to_csv(description, rows, suffix: str = "") -> str:
    """
    将 cursor 查询结果转为 CSV 风格字符串，便于 LLM 阅读。
    第一行表头，后续每行一条记录，逗号分隔。
    """
    columns = [desc[0] for desc in description]
    header = ",".join(columns)
    body = "\n".join(",".join(map(str, row)) for row in rows)
    return f"{header}\n{body}{suffix}"


def _audit(tool: str, query: str, ms: float, size: int, ok: bool) -> None:
    """SQL 审计日志，后续可改为结构化 JSON 写入 observability。"""
    status = "ok" if ok else "fail"
    print(f"[SQL Audit] tool={tool} ms={ms:.1f} size={size} status={status} query={query[:120]}")


@tool
def list_sql_tables() -> str:
    """
    列出 xiaoneng_db 中所有可用表。
    Agent 查数的第一步，用于了解有哪些 requirements/defects/iterations 等表。
    """
    hooks.report_tool("list_sql_tables")
    settings = get_settings()
    config = settings.mysql_config()
    if not config.get("user"):
        return "错误：数据库未配置，请检查 .env 中 MYSQL_* 项"

    start = time.perf_counter()
    try:
        with connect(**config) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SHOW TABLES")
                tables = cursor.fetchall()
                if not tables:
                    return "没有可用的表"
                names = [t[0] for t in tables]
                result = f"可用的表有：{', '.join(names)}"
                _audit("list_sql_tables", "SHOW TABLES", (time.perf_counter() - start) * 1000, len(result), True)
                return result
    except Error as e:
        _audit("list_sql_tables", "SHOW TABLES", (time.perf_counter() - start) * 1000, 0, False)
        return f"查询出现异常：{str(e)}"


@tool
def get_table_data(table_name: str) -> str:
    """
    预览指定表的前 100 行数据，用于了解列名和数据格式。
    表名经 validate_table_name 校验，SQL 使用反引号包裹防关键字冲突。
    """
    hooks.report_tool("get_table_data", {"table_name": table_name})
    ok, err = validate_table_name(table_name)
    if not ok:
        return f"错误：{err}"

    settings = get_settings()
    config = settings.mysql_config()
    start = time.perf_counter()
    sql = f"SELECT * FROM `{table_name}` LIMIT 100"
    try:
        with connect(**config) as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql)
                description = cursor.description
                if not description:
                    return f"数据表 {table_name} 为空"
                rows = cursor.fetchall()
                result = _rows_to_csv(description, rows)
                _audit("get_table_data", sql, (time.perf_counter() - start) * 1000, len(result), True)
                return result
    except Error as e:
        _audit("get_table_data", sql, (time.perf_counter() - start) * 1000, 0, False)
        return f"查询出现异常：{str(e)}"


@tool
def execute_sql_query(query: str) -> str:
    """
    执行自定义只读 SQL（SELECT/SHOW/DESCRIBE/EXPLAIN）。
    结果最多返回 100 行，防止 context 过长。
    """
    hooks.report_tool("execute_sql_query", {"query": query})
    ok, err = validate_readonly_sql(query)
    if not ok:
        return f"错误：{err}"

    settings = get_settings()
    config = settings.mysql_config()
    start = time.perf_counter()
    try:
        with connect(**config) as conn:
            with conn.cursor() as cursor:
                cursor.execute(query)
                description = cursor.description
                if not description:
                    return f"执行 SQL 无结果：{query}"
                rows = cursor.fetchall()[:100]
                result = _rows_to_csv(description, rows, "\n(结果已截断至100行)")
                _audit("execute_sql_query", query, (time.perf_counter() - start) * 1000, len(result), True)
                return result
    except Error as e:
        _audit("execute_sql_query", query, (time.perf_counter() - start) * 1000, 0, False)
        return f"查询出现异常：{str(e)}"
