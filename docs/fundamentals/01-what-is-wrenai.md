# 01：WrenAI 是什麼

驗證基準：`Canner/WrenAI@9a0f0324307442cb523b43838f391add328b78f9`

## 一句話

current WrenAI 是給 agent 使用的 open context + semantic SQL layer。它讓團隊把
資料庫的業務語意寫成可版本控制的 MDL，讓 agent 先取得適量 context，再對 MDL
寫 SQL；deterministic engine 把該 SQL 展開成 data source 能執行的方言。

它不是一個「輸入自然語言，內建 LLM 自動回 SQL」的單體服務。

## 它解決哪個問題

只把 raw schema 丟給 LLM，仍缺少：

- 哪張近似表才是 canonical source；
- 計算欄位與 metric 的正式定義；
- 關係要如何 join；
- 哪些欄位可見、哪些 row policy 要套用；
- 團隊確認過的 NL-to-SQL 範例；
- agent 應依什麼順序 fetch、plan、execute、repair。

WrenAI 把問題拆成不同的 artifact 和 runtime：

| 問題 | WrenAI 的位置 |
|---|---|
| 資料模型與 deterministic 語意 | MDL |
| 團隊操作規則與 caveat | `knowledge/rules/*.md` |
| 已確認的問題與 SQL | `knowledge/sql/*.md` |
| 找到相關 schema / example | memory |
| agent 的操作程序 | skills |
| SQL 展開與 access-control primitives | `wren-core` |
| 方言與資料庫 I/O | Python planner + connectors |

這個分離是核心設計，不應全部叫做 RAG。

## Agent 與 engine 的責任

### Agent / LLM

- 將自然語言問題拆成資料需求；
- 決定要 fetch 哪些 context；
- 處理 ambiguity，必要時向使用者追問；
- 產生對 MDL 的 SQL；
- 根據 structured error 修正；
- 把確認成功的 NL-to-SQL pair 存回 durable knowledge。

### Deterministic WrenAI

- 讀取並驗證 MDL 結構；
- 解析 SQL 與識別所用 model/view；
- 展開 table reference、`ref_sql`、calculated field、relationship；
- 執行 strict-mode / denied-function policy；
- 執行 MDL 中的 RLAC/CLAC primitives；
- 轉成目標方言並交給 connector；
- 回傳 Arrow table 或明確錯誤。

「agent 應遵守某規則」不等於「engine 一定強制該規則」。例如
`knowledge/rules/` 是 agent-facing context；它不會在一般 project build 中自動變成
`dry-plan` filter。可重跑證據見
[`experiments/03-rules-boundary`](../../experiments/03-rules-boundary/)。

## `main` 與 `legacy/v1`

| | current `main` | `legacy/v1` |
|---|---|---|
| 主要形態 | Agent-native CLI / Python SDK / Rust engine / GenBI tools | Docker chat-first BI application |
| LLM orchestration | 外部 coding agent 或 SDK integration | repository 內的 generation/retrieval pipelines |
| 語意引擎 | current development line | frozen application architecture |
| 本 repository 用途 | 權威實作 | 歷史對照 |

網路文章若談 `wren-ai-service/src/pipelines/`，通常是在講 legacy；若談
`core/wren/src/wren/engine.py` 與 `core/wren-core`，才是 current main。

詳細歷史背景保留在
[`deep-dives/legacy-v1-architecture.md`](../deep-dives/legacy-v1-architecture.md)。

## 最小心智模型

```text
Business question
    |
    v
Agent reads workflow (skill)
    |
    +--> context instructions (rules)
    +--> memory fetch (schema slice)
    +--> memory recall (confirmed examples)
    |
    v
Agent writes SQL against MDL names
    |
    v
WrenEngine.dry_plan / query
    |
    +--> sqlglot parse + policy
    +--> query-scoped manifest extraction
    +--> PyO3 SessionContext
    +--> Rust semantic analysis
    +--> CTE rewrite + target dialect
    |
    v
Connector -> database
```

## 哪些東西不能混為一談

- **MDL vs rules**：MDL 是 engine 可分析的 typed semantic contract；rules 是給
  agent 讀的 Markdown。
- **memory source vs index**：`knowledge/sql/` 是 durable source；LanceDB 是可重建
  derived artifact。
- **dry-plan vs dry-run**：前者不連資料庫，只顯示 planned SQL；後者交給 connector
  做 live validation。
- **strict mode vs RLAC**：strict mode 擋未建模 table / denied function；RLAC/CLAC
  是 MDL access-control semantics。
- **skill vs tool**：skill 描述流程；CLI/SDK command 才執行動作。

## Source anchors

| Claim | Source |
|---|---|
| Python facade 與 plan/execute split | `core/wren/src/wren/engine.py::WrenEngine` |
| Project artifacts 與 build | `core/wren/src/wren/context.py::build_manifest`, `build_json` |
| Rules 是 agent context | `core/wren/src/wren/context.py::load_rules` |
| Memory 的 full/search strategy | `core/wren/src/wren/memory/store.py::MemoryStore.get_context` |
| Rust semantic engine | `core/wren-core/core/src/mdl/mod.rs::WrenMDL`, `transform_sql` |
| Agent workflow content | `skills/wren/SKILL.md`, `core/wren/src/wren/skills_content/` |

## 可能使本章失效的變更

- upstream 新增內建 NL-to-SQL service；
- `knowledge/rules` 被編譯成 typed engine policy；
- legacy branch 恢復 feature/security maintenance；
- query path 不再經過 `WrenEngine` / `SessionContext`。
