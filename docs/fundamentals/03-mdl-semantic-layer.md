# 03：MDL 與 Semantic Layer

驗證基準：`Canner/WrenAI@9a0f032`

## 從 database schema 到可問的業務表面

```text
physical tables / files
       |
       v
Wren project YAML
  models / relationships / views / cubes
       |
       v  wren context build
target/mdl.json
       |
       v  serde + WrenMDL analysis
typed semantic graph
       |
       v  query-specific planning
expanded executable SQL
```

Raw schema 能告訴 agent 欄位存在，卻不能可靠表示 canonical table、calculated
field、approved relationship 或 row/column access semantics。MDL 把可編譯的部分
變成 typed、reviewable contract。

## 四個主要構件

| Construct | 用途 | Deterministic effect |
|---|---|---|
| Model | 將 logical name 映射到 `tableReference` 或 `refSql`，宣告 columns | query 中的 model/column 會展開到 physical source |
| Relationship | 宣告 model 間 join condition 與 cardinality | relationship-aware expression 可由 analyzer 解出 |
| View | 定義可重用 semantic query surface | planner 展開為依賴 model 的 query |
| Cube | 定義 dimension / measure query interface | cube query 可編成 SQL |

RLAC/CLAC 也屬於 typed MDL semantics；`knowledge/rules/*.md` 不屬於。

## 哪些資訊是 deterministic

- physical table / `ref_sql` mapping；
- exposed columns 與 calculated expression；
- relationship condition；
- view statement；
- cube dimensions/measures；
- typed access-control declarations；
- SQL identifier resolution、semantic expansion、target dialect generation。

## Agent 仍要推論什麼

- 使用者問題的 intent 與 time grain；
- 哪些 model/metric 最符合問題；
- ambiguity 是否需要澄清；
- Markdown rules 如何影響 SQL；
- 哪個 confirmed query example 值得重用；
- query failure 後的 repair strategy。

MDL 降低 agent 的自由度，但沒有消除自然語言推理。

## Project build boundary

`core/wren/src/wren/context.py`：

1. `load_project_config`、`load_models`、`load_views`、`load_relationships`、
   `load_cubes` 讀 source files。
2. `build_manifest` 組成 snake_case manifest。
3. `build_json` 轉成 engine wire format 並設定 `layoutVersion`。
4. `save_target` 寫入 `target/mdl.json`。

`build_manifest` 的 docstring 明確說 instructions 不在 manifest 中。這是
`knowledge/rules` 不會自動變成 engine filter 的第一個 boundary。

## Validate once, at the edge

current upstream 的 Contribution Bar 特別要求先判斷資料在哪一側：

```text
raw JSON / YAML / external API
        |
        | Python 可能在 dereference 前就需要 shape validation
        v
ManifestExtractor / SessionContext
        |
        | Rust serde 成功
        v
typed Manifest invariant
```

### 真正的 edge

`convert_mdl_to_project(mdl_json)` 直接收到 `wren context init --from-mdl` 的
user-supplied JSON。若它在 Rust serde 前存取 nested field，shape guard 是 reachable。

這不代表任何 guard placement 都合理。PR #2567 把 legacy view 防護放在
`validate_project` consumer；review 追出 `_load_views_v1` 的四個 consumers 後，
真正的 crash fix 由 PR #2604 放回共同 loader，並只讓 user-facing validator 另讀
raw rows 以產生精確錯誤。raw converter 的 `TypeError` 則被留作較小的訊息改善，
沒有和 loader defect 混成同一修正。

### 已被保證的內部狀態

`ManifestExtractor` 或 `SessionContext` 成功建立後，`Manifest`、`Model`、`Column`
已是 Rust typed values。下游再為「model 可能是 integer」加 defensive guard，
通常是 unreachable dead code。

PR #2602 review 的關鍵教訓就是：看起來像 edge 的 function，不一定由 raw caller
呼叫。必須往上追 caller。

## Malformed MDL 會發生什麼

失敗點取決於入口：

- malformed YAML：Python YAML loader / project validator；
- raw manifest JSON 的 missing/wrong-shaped field：可能先在 Python consumer 失敗，
  或在 PyO3/Rust serde 拒絕；
- 結構正確但 semantic reference 錯：WrenMDL/DataFusion analysis；
- SQL 使用不存在 column/model：planning error；
- physical table/permission 問題：connector/database。

因此「MDL validation」不是一個單一 function，而是一組不同 boundary。

[`experiments/07-validation-boundaries`](../../experiments/07-validation-boundaries/)
以同類 non-mapping value 比較 v1 YAML、raw import JSON 與 Rust serde 的實際結果。

## Semantic enforcement

`WrenEngine._plan` 先用 sqlglot 找到 table references，透過
`ManifestExtractor.extract_by` 取得 query-scoped manifest，再建立
`SessionContext`。`CTERewriter` 呼叫 `SessionContext.transform_sql`，由 Rust
analyzer 把 model semantics 展開，最後再生成 target-dialect SQL。

這個 enforcement 是 deterministic；agent 不能靠 prompt 覆寫 calculated-field
definition 或 typed relationship。

## 一個實用分類

| 知識 | 放 MDL？ | 理由 |
|---|---|---|
| `revenue = price * quantity` | 是 | 可編譯 calculated field |
| orders -> customers join | 是 | typed relationship |
| 永遠不可見的敏感 column | 是，或 DB privilege | 必須 engine/DB enforce |
| 「報表預設排除測試帳號」 | 視保證需求 | 只寫 rules 是 agent convention；要保證需 typed/DB policy |
| 「status=4 代表 churned」 | column description / rules | 給 agent 理解值 |
| 已確認問題與 SQL | `knowledge/sql/` | example，不是 schema contract |

## Source anchors

- `core/wren/src/wren/context.py::build_manifest`, `build_json`,
  `convert_mdl_to_project`
- `core/wren-core-base/src/mdl/manifest.rs`
- `core/wren-core-py/src/manifest.rs::to_manifest`
- `core/wren-core-py/src/extractor.rs::PyManifestExtractor`
- `core/wren-core-py/src/context.rs::PySessionContext`
- `core/wren-core/core/src/mdl/mod.rs::WrenMDL`, `transform_sql`
- `core/wren-core/core/src/logical_plan/analyze/`

## Falsifier

若 rules 進入 typed manifest、Rust deserialization 移出 PyO3 boundary，或 Python
planner 不再做 manifest extraction，本章的 boundary 需要重驗。
