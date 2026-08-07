# 04：Query Lifecycle

驗證基準：`Canner/WrenAI@9a0f032`

本章只追 current `main` 的 deterministic query path。自然語言如何變成初始 SQL
由外部 agent 負責。

## Path 0：Agent 準備 SQL

典型 skill 會要求：

1. `wren context instructions` 取得 business rules；
2. `wren memory fetch -q ...` 取得 relevant schema；
3. `wren memory recall -q ...` 找 confirmed examples；
4. agent 產生對 MDL model names 的 SQL；
5. 先 `dry-plan` / `dry-run`，再 execute。

這些步驟是 workflow，不是 `WrenEngine` 內的 hidden RAG pipeline。

## Path 1：CLI 到 `WrenEngine`

CLI 解析：

- SQL；
- compiled `target/mdl.json`；
- active profile / connection info；
- data source；
- config，例如 `strict_mode` 與 `denied_functions`。

接著建立 `WrenEngine(manifest_str, data_source, connection_info, ...)`。

三個 public operation：

| Method | DB round trip | Result |
|---|---:|---|
| `dry_plan` | 否 | expanded target-dialect SQL |
| `dry_run` | 是 | connector/database validation，無 rows |
| `query` | 是 | `pyarrow.Table` |

## Path 2：`WrenEngine._plan`

`core/wren/src/wren/engine.py::WrenEngine._plan` 的順序：

1. 將 query properties 轉為 hashable `frozenset`。
2. 用 target dialect 的 sqlglot parse SQL。
3. 從 decoded manifest 收集 model 與 view names。
4. 若 strict mode 或 denied functions 啟用，呼叫 `validate_sql_policy`。
5. 依 quoted/unquoted identifier rules 解出 canonical names。
6. `ManifestExtractor.extract_by(tables)` 取得最小 manifest。
7. 將最小 manifest 重新編成 base64 JSON。
8. `get_session_context(...)` 取得或重用 PyO3 context。
9. 建立 `CTERewriter` 並呼叫 `rewrite(sql)`。

若前半部 extraction 在非-strict path 失敗，會 fallback 到 full manifest。若
strict/denied policy 啟用，parse/policy 錯誤會轉成 planning `WrenError`，不應用
fallback 掩蓋。

## Path 3：Session cache

`core/wren/src/wren/mdl/__init__.py::get_session_context` 使用：

```python
@lru_cache(maxsize=32)
```

cache key 包含 effective query-scoped manifest、function path、properties 與 data
source。PR #2628 的原因是不同 table subsets 會產生不同 key；unbounded cache
會讓 process lifetime memory 隨 query combinations 增長。

重要 invariant：不要把可變 runtime state 寄託在 cached session。LRU eviction 後
同一 key 會得到 fresh context。

## Path 4：Rust semantic transformation

PyO3 `SessionContext.transform_sql` 進入 `wren-core`：

- parse SQL；
- 用 `WrenMDL` 與 analyzer rules 取代 logical table scans；
- 展開 calculated fields、models、views、relationships；
- 套用 typed access-control rules；
- 產生 semantic SQL。

`CTERewriter` 再把各 model expansion 注入 query CTE，最後由 sqlglot 生成 target
dialect。

## Path 5：Execution

`query()`：

```text
dry_plan
-> connector factory
-> connector.query(planned_sql, limit)
-> pyarrow.Table
```

`dry_run()` 則呼叫 connector 的 `dry_run(planned_sql)`。

limit 的語意屬 connector / caller contract，不是 Rust semantic planner 的通用
安全上限。詳見 deep dive 與 `experiments/05-result-limits`。

## Error phases

| Phase | Example | Owner |
|---|---|---|
| Project/config | target missing、profile malformed | CLI/context |
| SQL planning | invalid MDL reference、blocked function | Python planner / Rust core |
| SQL dry run | target DB rejects planned SQL | connector |
| SQL execution | permission、timeout、runtime DB error | connector/database |

`WrenEngine` 保留原有 `WrenError`；一般 exception 會包成帶
`ErrorPhase.SQL_PLANNING`、`SQL_DRY_RUN` 或 `SQL_EXECUTION` 的 `WrenError`。
已 structured 的 connector error 不會被重新包裝；arbitrary connector exception
則保留 planned SQL metadata 與 in-process cause。config 與 Typer misuse 是不同
signal channel，詳見
[`experiments/09-error-recovery`](../../experiments/09-error-recovery/)。

## 可重跑

[`experiments/01-query-lifecycle`](../../experiments/01-query-lifecycle/) 建立單一
orders model，執行 `dry_plan`，檢查 physical table CTE 與 calculated field 是否
出現在結果。

## Source anchors

- `core/wren/src/wren/engine.py::WrenEngine`
- `core/wren/src/wren/mdl/__init__.py::get_session_context`
- `core/wren/src/wren/mdl/cte_rewriter.py::CTERewriter`
- `core/wren-core-py/src/context.rs::PySessionContext::transform_sql`
- `core/wren-core/core/src/mdl/mod.rs::transform_sql`
- `core/wren/src/wren/connector/factory.py::get_connector`

## Falsifier

任何 query order、fallback policy、cache key、connector limit contract 的變更，都
需要重跑 lifecycle experiment，不應只看 function 名稱仍存在。
