# R1 失败隔离实现计划

> **For agentic workers:** TDD；先红后绿；小步提交逻辑。

**Goal:** 结构化工具结果 + ContextVar 失败收集 + partial_success 决策。

**Tech:** Python 3.12、stdlib unittest（无 pytest 依赖亦可）。

## Task 1: tool_result + failure_steps（TDD）

- [ ] RED: `tests/test_tool_result.py`
- [ ] GREEN: `tools/tool_result.py`, `context/failure_steps.py`

## Task 2: TaskStore partial_success

- [ ] RED: `tests/test_task_store.py`
- [ ] GREEN: 扩展 `api/task_store.py`

## Task 3: 改造工具返回值

- [ ] 各 `tools/*.py` 使用 format_ok / format_error

## Task 4: Runner + Monitor + Prompt

- [ ] runner 结束时 decide + mark_*
- [ ] monitor step_failed / degraded
- [ ] prompts.yml

## Task 5: 验证

- [ ] `python -m unittest discover -s tests -v`
