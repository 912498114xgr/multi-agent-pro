"""
新手教学：await vs create_task（模拟你们的任务接口）

运行：
  python tmp_asyncio_tutorial.py

对照口诀：
  create_task = 登记工单，调用方立刻往下
  await       = 当前工单跟进菜谱，跟完才往下
  挂起        = 菜谱内部等 I/O 时，调度员去推别的工单
"""

from __future__ import annotations

import asyncio
import time

# 用「相对启动的秒数」打印，方便看交错顺序
_t0 = time.perf_counter()


def log(who: str, msg: str) -> None:
    print(f"t={time.perf_counter() - _t0:4.1f}s | {who:<12} | {msg}")


# ---------- 模拟：模型流式输出（像 astream）----------

async def fake_astream(query: str):
    """sleep = wait model; yield = one chunk (like astream)."""
    chunks = ["plan-tools", "call-subagent", f"final:{query}"]
    for i, text in enumerate(chunks, 1):
        log("astream", f"waiting model for chunk#{i} ...")
        await asyncio.sleep(1.0)  # suspend: loop can run OTHER tasks
        log("astream", f"got chunk#{i}: {text}")
        yield text


# ---------- like _consume_agent_stream ----------

async def consume_agent_stream(query: str) -> str:
    final = ""
    async for chunk in fake_astream(query):
        log("consume", f"handle chunk -> {chunk}")
        if chunk.startswith("final:"):
            final = chunk
    log("consume", "stream done, return")
    return final


# ---------- like run_deep_agent ----------

async def run_deep_agent(query: str, thread_id: str) -> None:
    log("agent", f"[{thread_id}] setup (sync, fast)")
    result = await consume_agent_stream(query)  # follow until done
    log("agent", f"[{thread_id}] mark_done -> {result}")


# ---------- like _run_task_background ----------

async def run_task_background(query: str, thread_id: str) -> None:
    log("bg", f"[{thread_id}] background task START")
    await run_deep_agent(query, thread_id)  # must finish before next line
    log("bg", f"[{thread_id}] background task END")


# ---------- other work on same loop (WS / other HTTP) ----------

async def other_traffic() -> None:
    for i in range(1, 7):
        await asyncio.sleep(0.5)
        log("other", f"side work #{i} (like WS push / other HTTP)")


# ---------- like _start_task + POST /api/tasks ----------

async def http_create_task(query: str, thread_id: str) -> dict:
    log("http", f"POST received, id={thread_id}")
    # create_task: schedule and CONTINUE (do not wait agent)
    asyncio.create_task(
        run_task_background(query, thread_id),
        name=f"agent-{thread_id}",
    )
    log("http", "create_task done, return started NOW")
    return {"status": "started", "thread_id": thread_id}


async def main() -> None:
    traffic = asyncio.create_task(other_traffic(), name="other")

    resp = await http_create_task("weekly-report", "T1")
    log("http", f"client already got response: {resp}")

    await asyncio.sleep(0.2)
    log("http", "GET /tasks/T1 (poll status, not blocked)")

    await traffic
    await asyncio.sleep(0.1)
    pending = [t for t in asyncio.all_tasks() if t.get_name().startswith("agent-")]
    if pending:
        await asyncio.gather(*pending)

    log("main", "ALL DONE — read timestamps top to bottom")


if __name__ == "__main__":
    asyncio.run(main())
