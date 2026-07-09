# 第 4 章:安全性與可治理的實際落地

> 深挖優先序:**第 5**。`policy.py` 是被官方文件低估的實質亮點,值得看原始碼;
> 但「governed」一詞的邊界(哪些內建、哪些預設關、哪些要外部補)必須釐清。

一句話結論:**WrenAI 的「governed text-to-SQL」是「一組治理原語(primitives)的組合」——
SQL firewall + RLAC/CLAC + dry-plan + row limit——而不是一個開箱即用的完整治理平台。
其中最強的 SQL firewall 預設是關的,審計/審批/rate limit 官方標為「未來」。**

---

## 4.1 「governed」在原始碼層級到底是什麼

拆開來,WrenAI 的治理由這幾個具體機制構成,強度差很多:

| 機制 | 是什麼 | 強度 | 預設 | 證據 |
|---|---|---|---|---|
| RLAC / CLAC | row/column 存取控制,引擎注入 | 強(deterministic) | 需定義規則 + 傳身份 | 第 3 章 |
| SQL firewall(strict mode) | 只允許 MDL 內的表 + 擋危險函式 | 強 | **關(`strict_mode=False`)** | `policy.py`、`config.py` |
| dry-plan / dry-run | 執行前驗證 SQL 能否 planning/跑 | 中(需呼叫端主動用) | — | `cli.py`、`engine.py` |
| row limit | 限制回傳列數 | 弱(CLI/API 預設無上限;SDK 工具路徑有 100/1000,§2.1b) | 無(SDK 除外) | 第 2 章 |
| MDL 由人審核 | 語意定義版控、review | 弱(流程治理,非技術強制) | — | MDL as YAML in git |
| knowledge/rules 業務規則 | 純 prompt 素材,LLM 讀不讀隨緣 | **最弱(prompt 治理,見 4.1b)** | — | `context.py::load_rules` |
| audit log / 審批 / rate limit | — | **不存在**(README 標為 What's next) | — | README |

所以「governed」**不是**單一的 query 審核流程,也**不只是**「semantic 定義人審過」這種
弱治理——它比後者強(有 RLAC + firewall 的技術強制),但比「完整治理平台」弱
(關鍵護欄預設關、審計缺席)。

---

## 4.1b 官方文件的一處誇大:knowledge/rules 是 prompt 治理,不是引擎治理(2026-07 核驗)

官方 `docs/core/concepts/correctness.md:57` 宣稱 `wren dry-plan` 的輸出會包含:

> "Policy filters from your business rules (`knowledge/rules/`) injected"

**原始碼不支持這句話。** 核驗路徑:

- `knowledge/rules/*.md` 的唯一消費者是 `load_rules()`(`context.py:726`),
  它把 markdown 檔**串接成純文字**,由 `wren context instructions` 印到 stdout
  (`context_cli.py:777`,docstring 自己寫「for LLM consumption」)。
- `engine.py`(planning/dry-plan 的家)**沒有任何地方** import 或呼叫
  `load_rules` / `load_knowledge_rules`;grep 整個 engine 路徑找不到
  `knowledge` 字樣。
- 引擎在 dry-plan 時真正注入的 filter 只有一種:**MDL 裡的 RLAC**
  (`plan.rs::build_rlac_filter`,第 3 章)。

所以正確的分級是:

| 治理載體 | 寫在哪 | 誰強制 | 強度 |
|---|---|---|---|
| RLAC/CLAC | MDL(`models/*.yml` 的 access control 區塊) | **Rust 引擎,deterministic** | 強 |
| 「一律過濾 `is_deleted=false`」這類業務規則 | `knowledge/rules/*.md` | **沒人**——只是 prompt 素材,LLM 讀了不一定照做,prompt injection 可推翻 | 弱 |

**教材判定**:官方把「進 prompt 的建議」和「進 plan 的強制」用同一句話帶過,
是行銷式含糊。評估時的紅線:**任何有安全/合規意涵的規則(資料範圍、過濾條件、
遮蔽)必須寫成 MDL 的 RLAC/CLAC,寫進 knowledge/rules 的只能當 UX 提示。**
「這條規則寫錯地方」在 WrenAI 裡是安全等級的差異,不是風格差異。

---

## 4.2 SQL Firewall(`policy.py`)—— 被低估的亮點,但預設關閉

這是本章最實質的部分。`policy.py`(437 行,對應 issue #2409)是一道真正的 SQL 防火牆。

### 開關與進入點
```python
# engine.py::_plan
if self._config.strict_mode or self._config.denied_functions:
    validate_sql_policy(ast, queryable_names, self._config)
```
```python
# policy.py
def validate_sql_policy(ast, model_names, config):
    if config.strict_mode:
        _check_data_readers(ast)        # 擋資料讀取型函式(所有位置)
        _check_tables(ast, model_names, config.allowed_source_functions)  # 表白名單
    if config.denied_functions:
        _check_functions(ast, config.denied_functions)   # 自訂黑名單
```

**⚠️ 關鍵:`strict_mode` 預設是 `False`**(`config.py` 行 32)。
不開 strict mode,這道防火牆整個不啟用,text2SQL 就退化成「LLM 產什麼就跑什麼」
(僅剩 MDL 展開,沒有表白名單、沒有危險函式防護)。

### 開了之後擋什麼(三類威脅,防護扎實)

1. **表白名單(fail-closed)**:`_check_tables` 只允許 MDL manifest 內的 models/views,
   任何未知表/未知 table-valued function 在 source 位置一律拒絕。這防「LLM 幻覺出
   不存在的表」與「存取未授權的表」。

2. **資料讀取型函式(全 AST 位置封鎖)**:`_check_data_readers` + `_DATA_READER_NAMES`
   黑名單擋掉:
   - `read_csv('/etc/passwd')` / `pg_read_file` / `load_file` → **本地檔案路徑穿越**
   - `read_parquet('s3://...')` / `url(...)` → **SSRF / 資料外洩**
   - `dblink` / `postgres_scan` / `mysql_query` → **橫向移動到其他資料庫**
   
   而且是**在每個 AST 位置檢查**(不只 FROM/JOIN),連藏在 projection/subquery/
   `UNNEST(read_csv(...))` 裡的 reader 都擋(issue #2409 的補強)。

3. **DoS 生成器**:`generate_series(1, 1e12)` 這種會物化上兆列的生成器**預設封鎖**,
   只有 operator 用 `allowed_source_functions` 明確 opt-in 才放行。

4. **自訂黑名單**:`denied_functions` 讓 operator 額外封任何函式(縱深防禦)。

補一個 2026-07 核驗發現的細節,比初版描述**更強**:`config.py:28-30` 明文規定
data/file reader(`read_csv`、`dblink`…)**永遠不能**經 `allowed_source_functions`
放行——那個 opt-in 白名單只對 `generate_series` 類合成生成器有效。也就是說
「路徑穿越/SSRF/橫向移動」這三類在 strict mode 下沒有任何後門可開。

**判定(4.2)**:`policy.py` 的威脅模型很成熟(路徑穿越 / SSRF / 橫向移動 / DoS
都想到了),這是 WrenAI 治理的真本事。**但它預設關閉,是 opt-in。** 企業用一定要開
`strict_mode=true`,否則等於沒有這道牆。

證據:`core/wren/src/wren/policy.py`、`core/wren/src/wren/config.py`。

---

## 4.3 從 NL 到執行,可插入審核的關卡有哪些

沿著 pipeline 標出可治理的「關卡」,並註明內建 or 需外部:

```
自然語言問題
  │
  ① 身份注入(session property)     —— ⚠️ 需外部 gateway 提供(第 3 章)
  ▼
LLM/agent 產「邏輯 SQL」
  │
  ② SQL firewall (strict mode)      —— ✅ 內建,但預設關
  │    表白名單 / reader 封鎖 / DoS 生成器封鎖 / 自訂黑名單
  ▼
引擎展開 + RLAC/CLAC 注入
  │
  ③ row/column 存取控制             —— ✅ 內建,需定義規則 + 身份
  ▼
dry-plan / dry-run 驗證
  │
  ④ 執行前驗證(能否 planning/跑)   —— ✅ 內建原語,需呼叫端主動用
  ▼
連接器執行(單一 credential)
  │
  ⑤ row limit / timeout             —— ⚠️ 弱(CLI/API 無上限;SDK 工具除外,見第 2 章)
  ⑥ audit log / 審批 / rate limit   —— ❌ 不存在,需外部
  ▼
資料庫
```

**內建的關卡(②③④)品質不錯,但 ①⑤⑥ 需要外部系統補齊。** 特別是 audit log 與
approval workflow——對受監管產業(金融/醫療)幾乎是必須,而 WrenAI 目前沒有。

---

## 4.4 資料會不會外洩到 LLM API?—— 取決於架構與呼叫端實作

這直接決定能不能在「內部有敏感資料」的環境用。分兩層看:

### (a) 語意層 context → 會送給 LLM,但那是 metadata 不是資料
LLM 拿到的是 MDL 編出來的 DDL(表名、欄位名、description、計算式,見第 1 章),
這些是**schema 語意**,不是資料列本身。若你的欄位名/description 本身不敏感,這層
外洩風險低。

### (b) 查詢結果 rows → **可能會送給 LLM**(高風險點)
- **legacy/v1**:`sql_answer` 明確把 `rows: {{ sql_data.data }}` 放進 prompt
  (第 2 章)。所以「總結這些資料」會把**原始資料列送到 LLM API**。
- **main**:沒有內建摘要管線,是否把 rows 送 LLM **完全由外部 agent 決定**。
  走官方 SDK 工具的 agent,進 prompt 的 rows 被預設 limit=100 / 硬上限 1000 管住
  (第 2 章 §2.1b;16KB cap 只管 content 欄位、且僅 wren-langchain)——但那是
  「量」的控制,不是「該不該送」的 DLP 判斷;自己包 CLI/API 的 agent
  連量的控制都沒有。

**判定(4.4)**:schema 語意送 LLM 基本無法避免(這是 text2SQL 的前提);真正的敏感
資料外洩風險在「結果 rows 進 prompt」——legacy 會做、main 交給 agent。
**要在企業內部用,必須:(1) 用可自架/私有部署的 LLM 或有 DPA 的 API;(2) 在
gateway 層禁止/遮罩原始 rows 進 prompt,改走彙總。** WrenAI 本身不強制這件事。

---

## 4.5 對照企業 AI 安全框架(RBI / AV / DLP):覆蓋與缺口

把 WrenAI 現有機制對應到你在評估的既有安全流程:

| 你的框架關注 | WrenAI 覆蓋到嗎 | 缺口 / 需補強 |
|---|---|---|
| **存取控制(誰能看什麼資料)** | 部分:RLAC/CLAC 引擎層強制 | 身份注入需外部;單一共用 credential;無內建認證/SSO |
| **DLP(防敏感資料外流)** | 弱:firewall 擋 SSRF/檔案外讀,但**結果 rows 進 LLM prompt 不受管** | 需 gateway 層 DLP:遮罩/禁止 rows 進 prompt;私有 LLM |
| **AV / 惡意輸入** | 部分:strict-mode 擋危險 SQL 函式(路徑穿越/SSRF/橫向移動) | 預設關;需強制開 strict_mode |
| **RBI 類「隔離執行」概念** | 無對應:查詢直接對 DB 跑 | 需 gateway 隔離 + DB 只允許 service account 連 |
| **審計 / 合規(誰在何時查了什麼)** | ❌ 無 audit log | 需自建審計:記錄 (user, session props, 展開 SQL, 回傳列數) |
| **速率限制 / 濫用防護** | ❌ 無 rate limit | 需 gateway 層 rate limit |
| **審批流程(高風險查詢人工核准)** | ❌ 無 | 官方標為 What's next;需外部 workflow |

**總結**:WrenAI 覆蓋了「存取控制」與「惡意 SQL 防護」的技術基礎(且品質不差),
但在 **DLP(結果外洩)、審計、rate limit、審批** 這些企業合規必備項上是空白的,
且已覆蓋的部分很多預設關閉或需外部提供身份。它是「可被治理的引擎」,不是「治理平台」。

---

## 4.6 負責的模組(標註)

| 功能 | 檔案 |
|---|---|
| SQL firewall / policy | `core/wren/src/wren/policy.py` |
| 治理設定(strict_mode 等) | `core/wren/src/wren/config.py` |
| policy 進入點 | `core/wren/src/wren/engine.py::_plan` |
| dry-plan / dry-run | `core/wren/src/wren/cli.py`(行 449/537)、`engine.py` |
| RLAC/CLAC | 見第 3 章 |
| (legacy) 結果進 prompt | `wren-ai-service/src/pipelines/generation/sql_answer.py` |

---

## 4.7 動手驗證 🔬

```bash
# 1. 確認 strict_mode 預設關:不設 config 直接查一個 MDL 外的表/危險函式,應能通過
wren query --sql "SELECT * FROM read_csv('/etc/passwd')"   # 未開 strict → 觀察是否被擋

# 2. 開 strict_mode 後應被擋
#    在 ~/.wren config 設 {"strict_mode": true},重跑上面,預期 planning 階段 WrenError

# 3. 驗證 firewall 各類:read_parquet('s3://...') / dblink / generate_series(1,1e12)
```

---

**上一章** → [03 資料隔離](03-data-isolation.md)　|　**下一章** → [05 企業採用總評](05-enterprise-verdict.md)
