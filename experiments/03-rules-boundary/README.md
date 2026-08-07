# 03：Rules Boundary

## Question

`knowledge/rules/*.md` 是否由 project build 編進 engine manifest，並由 `dry_plan`
自動注入 SQL filter？

## Hypothesis

Rules 會被 `load_rules` 提供給 agent/memory，但一般 `build_json` 不包含它；
`WrenEngine` 因此無法自動注入該 Markdown filter。

## Setup

script 建 temporary v5 project：

- orders model 有 `is_deleted`；
- `knowledge/rules/general.md` 寫入 unique marker，要求 always filter；
- build manifest；
- 執行 `dry_plan("SELECT id FROM orders")`。

## Command

```bash
$WREN_PYTHON experiments/03-rules-boundary/run.py
```

## Observed result

在 `9a0f032`：

```text
rules-loaded-for-agent: True
rules-in-engine-manifest: False
filter-injected: False
```

planned SQL 只有 physical table projection，沒有 `is_deleted` predicate。

## Source explanation

`load_rules` 的 consumers 是 context CLI、memory index 與 MCP；`build_manifest` 明確
不包含 instructions。`WrenEngine._plan` 只收到 compiled manifest、SQL、properties
與 config。

## Conclusion

Rules 是 agent-facing governance。除非 agent 把規則寫進 SQL，或另有 typed/DB
policy，engine 不會因 Markdown 自動 enforce。這支持 candidate 001 的 docs fix。

## What could falsify this conclusion

Project build 將 rules 編成 typed manifest、`WrenEngine` 新增 rules argument，或
planner 明確載入 project rules。
