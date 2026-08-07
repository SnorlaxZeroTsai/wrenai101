# 08：Durable Memory Recall

## Question

沒有 LanceDB / sentence-transformers 時，confirmed NL-SQL memory 是否仍可被
public CLI 儲存、更新、bounded recall，且 reset 不會刪除 durable source？

## Hypothesis

`knowledge/sql/*.md` 是 source of truth。memory extra 缺席時 `store` 仍寫
Markdown，`recall` 使用 grep backend，same-NL update 重用同一檔案，`limit`
限制結果數，`reset` 沒有 derived index 可刪。

## Setup

script 建立 temporary schema-v5 project，明確模擬 optional memory store import
缺席並設定 `WREN_MEMORY_BACKEND=grep`。它透過 real Typer app：

1. store 一個 pair；
2. 用相同 NL 更新 SQL；
3. store 第二個 pair；
4. recall `revenue` with `--limit 1`；
5. 執行 status、check、reset，再 recall。

## Command

```bash
$WREN_PYTHON experiments/08-memory-recall/run.py
```

## Observed result

在 `9a0f032`：

```text
source-files: 2
Backend: grep
knowledge/sql: 2 pair(s)
grep backend ... always in sync
grep backend has no derived index
recall-after-reset == recall-before-reset
```

回傳 row 含 updated SQL、datasource、relative Markdown path 與 deterministic score；
`limit=1` 只回一筆。

## Source explanation

- `write_query_markdown` 以 canonical NL 決定 stable slug；相同 NL update in place；
- `GrepIndex.search` 用 token overlap 加 NL substring score，排序後套 `limit`；
- `memory recall` 由 `get_index` 選 backend，再標註 exact source path；
- grep backend 直接讀 Markdown，所以 `check` 永遠同步，`reset` 是 no-op。

## Conclusion

query memory 的 durability 不依賴 vector database。LanceDB 提供 semantic derived
index，但 confirmed examples 的可 review、可 version、可重建 contract 在
`knowledge/sql`。這也說明未確認 SQL 不應被 store：它會成為未來 agent 的 durable
context。

## What could falsify this conclusion

Markdown 不再是 source of truth、grep backend 被移除、same-NL dedup key 改變、
reset 開始刪 project knowledge，或 public recall 不再遵守 `limit`。
