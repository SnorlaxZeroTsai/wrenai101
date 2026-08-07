# 02：Repository 架構

驗證基準：`Canner/WrenAI@9a0f032`

## High-level call graph

```text
skills/wren/SKILL.md
  -> wren skills get <name>
  -> core/wren/src/wren/skills_content/<name>/SKILL.md
  -> agent invokes Wren CLI

core/wren (Python)
  -> wren-core-py (PyO3)
       -> wren-core (Rust + DataFusion)
            -> wren-core-base (typed MDL)
  -> connector/* -> database

sdk/wren-langchain and sdk/wren-pydantic
  -> core/wren public Python/CLI behavior

core/wren-core-wasm
  -> wren-core + wren-core-base
  -> browser DataFusion execution
```

## Module ownership

### `core/wren`

| Field | Detail |
|---|---|
| Purpose | `wrenai` Python package、Typer CLI、project/context management、planning orchestration、connectors、optional memory/MCP |
| Entry points | `wren.cli:app`, `wren.engine.WrenEngine` |
| Important symbols | `WrenEngine._plan`, `CTERewriter.rewrite`, `build_json`, `validate_project`, `MemoryStore` |
| Who calls it | Humans, coding agents, LangChain/Pydantic integrations, MCP |
| What it calls | sqlglot, `wren_core.SessionContext`, connector factory, optional LanceDB |
| Invariant owned | CLI/project boundary、query orchestration、target dialect、connection lifecycle；不重複實作 Rust MDL semantics |

### `core/wren-core`

| Field | Detail |
|---|---|
| Purpose | Rust semantic engine，透過 DataFusion 做 MDL analysis、logical planning、optimization、SQL generation |
| Entry points | `mdl::transform_sql`, `create_wren_ctx`, `WrenMDL::analyze` |
| Important symbols | `WrenMDL`, `AnalyzedWrenMDL`, `ModelAnalyzeRule`, access-control analyzer |
| Who calls it | `wren-core-py`, `wren-core-wasm`, Rust tests/examples |
| What it calls | DataFusion 53、`wren-core-base` manifest types |
| Invariant owned | model/view/relationship/calculated-field semantic meaning and analyzer correctness |

### `core/wren-core-base`

| Field | Detail |
|---|---|
| Purpose | Python、Rust engine、WASM 共用的 MDL data model |
| Entry points | Rust types under `src/mdl/` |
| Important symbols | `Manifest`, `Model`, `Column`, `Relationship`, `View`, `RowLevelAccessControl`, `ColumnLevelAccessControl` |
| Who calls it | `wren-core`, `wren-core-py`, `wren-core-wasm` |
| What it calls | serde、sqlparser；optional PyO3 macro support |
| Invariant owned | serialized manifest shape、defaults、backward-compatible field evolution |

### `core/wren-core-py`

| Field | Detail |
|---|---|
| Purpose | 用 PyO3 把 Rust semantic engine 暴露給 Python |
| Entry points | Python module `wren_core` |
| Important symbols | `SessionContext`, `ManifestExtractor`, `to_json_base64`, Rust-to-Python error conversion |
| Who calls it | `core/wren` |
| What it calls | `wren-core`, `wren-core-base` |
| Invariant owned | FFI boundary、manifest deserialization、Python-visible exception contract |

### `core/wren-core-wasm`

| Field | Detail |
|---|---|
| Purpose | 在 browser 中以 WASM + DataFusion 執行本地/URL-backed data |
| Entry points | JS `WrenEngine.init`, `loadMDL`, `registerParquet`, `registerJson`, `query` |
| Important symbols | Rust `WrenEngine` in `core/wren-core-wasm/src/lib.rs`, TypeScript wrapper in `core/wren-core-wasm/sdk/src/index.ts` |
| Who calls it | Browser GenBI / embedded clients |
| What it calls | `wren-core`, `wren-core-base`, Arrow, DataFusion |
| Invariant owned | Browser-native table registration、single-thread execution、WASM/JS error and result boundary |

### `skills`

| Field | Detail |
|---|---|
| Purpose | 發現 current CLI 所提供的 agent workflows |
| Entry points | `skills/wren/SKILL.md` discovery stub |
| Important symbols/files | `skills/index.json`, `skills/AUTHORING.md`, stub command examples |
| Who calls it | 支援 skill installation 的 coding agents |
| What it calls | `wren skills list/get` |
| Invariant owned | Stub 要小、穩定，不能複製整份可能與 installed CLI 漂移的 workflow |

真正的 served workflow 在 wheel 內：
`core/wren/src/wren/skills_content/`。`skills` repository directory 與 packaged
content 的角色不同。

### `sdk/wren-langchain` 與 `sdk/wren-pydantic`

| Field | Detail |
|---|---|
| Purpose | 將 Wren query/context primitives 包裝成 framework-native agent tools |
| Entry points | 各 package README 與 Python tool classes |
| Important symbols | query/context tool wrappers、result serialization/limits |
| Who calls it | LangChain 或 Pydantic AI applications |
| What it calls | Wren Python API |
| Invariant owned | Framework tool schema、agent-facing bounded output；不擁有 MDL semantics |

upstream 目錄名是 `sdk/`，不是 `sdks/`。

## 一次 query 的 ownership handoff

1. `core/wren/src/wren/cli.py` 解析 command、project 與 profile。
2. `WrenEngine` 擁有 orchestration。
3. `ManifestExtractor` 將 full manifest 縮成 referenced subset。
4. `SessionContext` 跨過 PyO3。
5. `wren-core` 分析 MDL semantic plan。
6. `CTERewriter` 把 expanded model SQL 插回 target-dialect query。
7. connector 執行並回傳 `pyarrow.Table`。

任何修正都要先判斷 invariant 屬於哪一層。例如：

- raw YAML shape error：Python context edge；
- 成功 serde 後的 `Model.name` 型別：Rust typed invariant；
- Postgres limit syntax：connector；
- agent 引用不存在的 flag：served-content validation。

## Source anchors

- `core/wren/.claude/CLAUDE.md`
- `core/wren-core/.claude/CLAUDE.md`
- `core/wren-core-base/.claude/CLAUDE.md`
- `core/wren-core-py/.claude/CLAUDE.md`
- `core/wren-core-wasm/.claude/CLAUDE.md`
- `core/wren/src/wren/engine.py::WrenEngine`
- `core/wren-core-py/src/context.rs::PySessionContext`
- `core/wren-core/core/src/mdl/mod.rs`

## Falsifier

若 module entry point、package dependency direction 或 query ownership 改變，這張
map 必須重畫，不能只更新版本號。
