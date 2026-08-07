# 01：Query Lifecycle

## Question

一條寫在 MDL model 上的 SQL，是否由 `dry_plan` deterministic 展開到 physical
table 與 calculated-field expression？

## Hypothesis

`WrenEngine._plan` 會將 `orders.order_key` 展開為 physical `main.orders` 上的
`concat(...)` expression，且不需要 database connection。

## Setup

使用 pinned upstream 的 `wrenai` development environment。script 內建最小 MDL
manifest。

## Command

```bash
$WREN_PYTHON experiments/01-query-lifecycle/run.py
```

## Observed result

在 `9a0f032`：

- output 含 `"main".orders`；
- output 含 calculated expression；
- `dry_plan` 沒有打開 connector。

## Source explanation

`WrenEngine._plan` -> `ManifestExtractor.extract_by` -> cached `SessionContext` ->
`CTERewriter.rewrite` -> Rust `transform_sql`。

## Conclusion

model mapping 與 calculated-field expansion 是 deterministic semantic planning，
不是 agent 在 prompt 中重寫 physical SQL。

## What could falsify this conclusion

Planner 改為 server-side service、calculated fields 不再經 Rust core，或
`dry_plan` 開始要求 live connector。
