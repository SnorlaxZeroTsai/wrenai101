# 第 1 章:text2SQL 的真實分工邊界

> 深挖優先序:**第 4**(最多人講、但多半把兩套架構講混了)。
> 這章的價值不是「新資訊」,而是**正本清源**:用原始碼證明 LLM 到底做了什麼、
> 沒做什麼,以及 WrenAI 靠什麼(而不是靠 LLM 更聰明)來降低 SQL 生成錯誤。

破除的表層說法:「WrenAI 用 RAG 把 schema 塞給 LLM,叫它生 SQL」。
真相要拆成三個問題:(1) LLM 拿到的 context 是什麼?(2) 引擎和 LLM 各做哪一半?
(3) 常見錯誤靠什麼壓下來?

---

## 1.1 LLM 拿到的 context:不是原始 schema,是 MDL 編譯出來的「帶語意 DDL」

**結論:LLM 看到的不是資料庫原始 schema,而是從 MDL 生成、內嵌業務語意與計算邏輯
的 `CREATE TABLE` DDL。** 這是 WrenAI 準確度的核心來源。

### MDL 是什麼(語意契約)

MDL(Modeling Definition Language)是一份可版控的 YAML,編譯成 `target/mdl.json`。
官方定位:「Raw schemas describe storage. MDL describes meaning.」它定義:

- **Models**:邏輯資料集(對應實體表或一段 SQL)
- **Columns**:欄位、改名、型別、主鍵,以及 **calculated fields**(計算欄位)
- **Relationships**:模型間的 join 路徑(你的分析團隊信任的那條)
- **Views / Cubes / Metrics**:可重用的查詢介面與指標
- **RLAC / CLAC**:row/column-level 存取控制(見第 3 章)

證據:`main` `docs/core/concepts/what_is_mdl.md`;型別定義在
`core/wren-core-base/src/mdl/manifest.rs`。

### MDL 怎麼變成 LLM 的 context(legacy 生成邏輯,仍是最好的範本)

在 `legacy/v1` 的檢索管線,MDL 被編成帶「語意註解」的 DDL 再餵給 LLM。看實際 prompt:

```sql
-- 出自 wren-ai-service/src/pipelines/generation/utils/sql.py
CREATE TABLE orders (
  -- {"description":"A column that represents the timestamp when the order was approved.","alias":"_timestamp"}
  ...
  -- This column is a Calculated Field
  -- column expression: avg(reviews.Score)
  ...
  -- This column is a Calculated Field
  -- column expression: count(order_items.ItemNumber) > 1
)
```

重點:
- 每個欄位帶 `description` 與 `alias`,LLM 因此知道 `status=4` 是「退款」這種業務語意——
  這是原始 schema 給不了的。
- **Calculated Field 的展開式(`avg(reviews.Score)`)直接寫在註解裡**,LLM 只要在
  SELECT 用這個計算欄位名,不必自己拼 join + aggregate。這是把「容易錯的部分」
  從 LLM 手上拿走的關鍵設計。

### 檢索是「MDL 子集」而非全量

`db_schema_retrieval.py` 用 embedding 檢索與問題相關的表(`table_retrieval` /
`dbschema_retrieval`),再組成 DDL,並用 tokenizer 算 token、超量就剪
(`check_using_db_schemas_without_pruning`,`_token_count = len(encoding.encode(...))`)。
→ 給 LLM 的是「與問題相關的 MDL 子集」,不是把整個 schema 倒進 prompt。

證據:`legacy/v1` `wren-ai-service/src/pipelines/retrieval/db_schema_retrieval.py`。

**準確度影響**:LLM 不需要理解物理表結構、不需要自己找 join 路徑、不需要重寫指標公式——
這些高風險決策已被 MDL 預先固定。LLM 的任務被縮小成「對著一個乾淨的語意視圖寫 SQL」。

---

## 1.2 引擎 vs LLM 的分工邊界:哪些是 deterministic、哪些交給 LLM

這是本章最實質的部分。分工如下:

| 工作 | 誰做 | 是否 deterministic | 證據 |
|---|---|---|---|
| 自然語言 → 邏輯 SQL | **LLM / 外部 agent** | ❌ 機率性 | main 不含 LLM;legacy `generation/sql_generation.py` |
| relationship → 實際 JOIN | **Rust 引擎** | ✅ | `wren-core` MDL 展開 |
| calculated column → aggregate 子查詢 | **Rust 引擎** | ✅ | `plan.rs` lineage / calculation plan |
| 邏輯 SQL → 目標方言 SQL | **Rust 引擎 + sqlglot** | ✅ | `engine.py::dry_plan` 註解的轉換流程 |
| 只允許 MDL 內的表/欄位 | **引擎 + policy** | ✅ | `policy.py`、`extract_by` |
| row/column 存取控制 | **Rust 引擎** | ✅ | `access_control.rs`(第 3 章) |

### `dry_plan` 的展開流程(deterministic 的那一半)

`engine.py::dry_plan` 的 docstring 逐字說明轉換管線:

```
User SQL (target dialect, e.g. Postgres)
  → sqlglot parse (target dialect)
  → qualify_tables + normalize_identifiers + qualify_columns
  → identify referenced models and columns
  → per-model: wren-core transform_sql → Wren dialect SQL
  → per-model: sqlglot parse (Wren dialect) → inject as CTE
  → sqlglot generate (target dialect)
  → output SQL with model CTEs in target dialect
```

翻白話:LLM 產的是「對著 MDL 模型的邏輯 SQL」(例如 `SELECT total_revenue FROM orders`,
其中 `total_revenue` 是計算欄位)。引擎接手後:

1. 用 `wren-core`(Rust/DataFusion)把每個模型 `transform_sql` 展開成含 JOIN、
   aggregate、計算式的實體 SQL;
2. 把展開結果當 CTE 注入;
3. 再用 sqlglot 生成目標資料庫方言(Postgres/BigQuery/…)。

**所以「JOIN 怎麼接、計算欄位怎麼算、方言差異」全是引擎 deterministic 處理的,
不經 LLM。** LLM 只碰最上層的邏輯查詢意圖。

證據:`core/wren/src/wren/engine.py`(`dry_plan` / `_plan`,行 87–235)、
`core/wren/src/wren/mdl/cte_rewriter.py`(`CTERewriter`)。

---

## 1.3 對常見 LLM SQL 錯誤的防禦:靠架構,不是靠 LLM 更聰明

拆三種典型錯誤,對照 WrenAI 的防禦:

### (a) JOIN 錯誤(接錯表、接錯鍵、漏 join)
- **防禦**:relationship 在 MDL 預先定義,計算欄位的 join 由引擎展開。LLM 若只用
  MDL 暴露的欄位,根本沒機會手寫錯 join。
- **殘留風險**:若 LLM 產的邏輯 SQL 直接跨模型手寫 join(而非用預定義關係),
  仍可能錯。MDL 降低機率,不是消滅。

### (b) 欄位誤用(用了不存在或不該用的欄位)
- **防禦(強)**:strict-mode `policy.py` + `extract_by` 只讓 SQL 參照 MDL 內的
  models/views;參照不存在的表會在 planning 階段擲 `WrenError`,**不會送到 DB**。
  ```python
  # engine.py::_plan
  if self._config.strict_mode or self._config.denied_functions:
      validate_sql_policy(ast, queryable_names, self._config)
  ```
- **注意**:此防禦**預設關閉**(`strict_mode=False`,見第 4 章)。不開就退化成
  「LLM 自律」。

### (c) 聚合邏輯錯誤(平均的平均、fan-out 重複計數)
- **防禦**:指標與計算欄位在 MDL 用 metrics/cubes/calculated field 預先定義好正確
  公式(如 `count(order_items.ItemNumber)`),LLM 引用名稱即可,不必自己拼 aggregate。
  引擎的 lineage(`required_fields_map`)確保計算欄位依賴的欄位被正確帶入。
- **證據**:`plan.rs` 的 calculation plan / lineage 處理;legacy DDL 註解裡的
  calculated field 展開式。

### (d) 語法/方言錯誤 → 有明確的自我修正迴圈(legacy)
- legacy `generation/sql_correction.py`:先 dry-run,拿到 DB 錯誤訊息後,把
  「錯誤訊息 + schema + SQL」再餵回 LLM 要求修正:
  > "First, think hard about the error message, and figure out the root cause first...
  > Then, generate the syntactically correct ANSI SQL query to correct the error."
- main 對應能力:`wren dry-run` / `wren dry-plan` 提供「不回傳資料就驗證 SQL 能否
  planning/執行」的原語,讓外部 agent 自己做這個修正迴圈。

**小結**:WrenAI 降錯的主力是**把高風險決策 deterministic 化 + 用 dry-plan 驗證**,
而不是「祈禱 LLM 更強」。但要注意最強的那道欄位/表白名單(strict mode)預設是關的。

---

## 1.4 負責這段邏輯的模組(標註)

| 功能 | 檔案 |
|---|---|
| MDL 型別定義 | `core/wren-core-base/src/mdl/manifest.rs` |
| MDL 語意展開(邏輯 SQL → 實體 SQL) | `core/wren-core/core/src/logical_plan/**` |
| planning 協調 + 方言轉換 | `core/wren/src/wren/engine.py`、`mdl/cte_rewriter.py` |
| SQL 白名單/firewall | `core/wren/src/wren/policy.py` |
| (legacy) 檢索:MDL→DDL、embedding | `wren-ai-service/src/pipelines/retrieval/db_schema_retrieval.py` |
| (legacy) 生成 + 自我修正 | `wren-ai-service/src/pipelines/generation/{sql_generation,sql_correction}.py` |

---

## 1.5 動手驗證 🔬

```bash
# 1. 安裝 CLI
pip install wrenai   # 或用 repo 內 core/wren 的 uv 環境

# 2. 用 sample dataset 看「邏輯 SQL → 展開後的實體 SQL」
wren dry-plan --sql "SELECT total_revenue FROM orders" --mdl target/mdl.json
#   觀察輸出:應看到引擎把 total_revenue 展成含 JOIN/aggregate 的 CTE,
#   並轉成目標方言。這證明 1.2 的分工。

# 3. 驗證欄位白名單(需開 strict_mode)
#    在 config 開 strict_mode=true 後,查一個 MDL 沒定義的表,應在 planning 階段報錯。
wren dry-run --sql "SELECT * FROM some_table_not_in_mdl"
```

---

**上一章** → [00 兩套架構](00-two-architectures.md)　|　**下一章** → [02 大量結果處理](02-large-result-handling.md)
