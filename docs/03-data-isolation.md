# 第 3 章:使用者資料存取隔離

> 深挖優先序:**第 1(最高)**。這是「使用者操作到不屬於他的資料」這個具體風險的核心,
> 也是多租戶 BI 工具最常踩雷的地方,而官方文件對此講得最含糊。

一句話結論:**WrenAI 有一套真材實料、引擎層強制的 row/column-level 存取控制(RLAC/CLAC),
但它的安全性完全取決於「身份有沒有被正確傳進來」——而預設的 CLI 路徑根本沒接身份,
且底層是單一共用 DB credential。能力是真的,落地是危險的。**

---

## 3.1 存取控制粒度:row-level + column-level 都支援,而且是引擎「內建」強制

**這點值得先肯定:RLAC/CLAC 不是行銷詞,是 Rust 引擎裡真的實作的。**

### Row-Level Access Control(RLAC)

在 MDL 定義「條件 + 需要的 session property」。引擎在建 logical plan 時,把符合的
規則編成一個 `Filter` **注入到查詢計畫裡**:

```rust
// core/wren-core/core/src/logical_plan/analyze/plan.rs
let rlac_filter = self.build_rlac_filter(&model)?;   // 行 440
// ...
fn build_rlac_filter(&self, model) -> Result<Option<Expr>> {   // 行 467
    let mut combined = None;
    for rule in model.row_level_access_controls().iter() {
        if !validate_rule(&rule.name, &rule.required_properties, &self.properties)? {
            continue;   // 該規則需要的 session property 不在 → 跳過
        }
        let expr = build_filter_expression(..., &self.properties, rule)?;
        combined = Some(match combined { Some(acc) => acc.and(expr), None => expr });
    }
    Ok(combined)   // 多條規則 AND 合併
}
```

MDL 定義長這樣(來自官方 Rust 範例):

```rust
// core/wren-core/wren-example/examples/row-level-access-control.rs
.add_row_level_access_control(
    "multitenant",
    vec![SessionProperty::new_required("session_tenant_id")],
    "tenant_id = @session_tenant_id")     // ← 條件裡的 @xxx 是 session property
.add_row_level_access_control(
    "auth",
    vec![SessionProperty::new_optional("session_role", Some("'MEMBER'".to_string())), ...])
```

執行時傳入身份:

```rust
let mut properties = HashMap::new();
properties.insert("session_tenant_id", Some("'tenant-a'"));
properties.insert("session_user_id",  Some("'1003-u3'"));
properties.insert("session_role",     Some("'ADMIN'"));
transform_sql_with_ctx(&ctx, mdl, &[], properties.into(), sql).await?;
```

→ 效果:`SELECT * FROM documents` 會被引擎**自動改寫**成
`SELECT * FROM documents WHERE tenant_id = 'tenant-a'`。使用者無從繞過(除非能偽造
session property,見 3.3)。

`@session_tenant_id` 的值怎麼被安全代入?`build_filter_expression`
(`access_control.rs` 行 175)會把 `@name` 換成 property value,而且會檢查:
required property 缺失 → 報錯;值為 null/空 → 報錯。**不是字串拼接**,是 parse 成
DataFusion `Expr` 再併入 plan,降低注入風險。

### Column-Level Access Control(CLAC)

CLAC 在 `validate_clac_rule`(`access_control.rs` 行 534)判斷某欄位對當前 session
是否可見:規則綁一個 session property,用 `clac.eval(value)` 比對
(支援 `Equals/NotEquals/GreaterThan/...`,見 `wren-core-base/src/mdl/cls.rs`)。
不通過 → 該欄位被擋。還會遞迴檢查 calculated field 依賴的來源欄位
(`required_fields_map`),避免「用計算欄位繞過欄位遮蔽」。

證據:`core/wren-core/core/src/logical_plan/analyze/access_control.rs`(RLAC/CLAC 邏輯)、
`core/wren-core-base/src/mdl/cls.rs`(CLAC 運算子)、`plan.rs`(注入點)。

**判定(3.1)**:粒度足夠(row + column),而且是**引擎在 plan 層強制**,不是靠
LLM 自律、也不是靠「semantic 定義人工審過」這種弱治理。這是 WrenAI 最值得信任的部分。

---

## 3.2 「內建強制」vs「靠底層 DB RLS」:WrenAI 是前者(重要區分)

你問的關鍵區分:是 WrenAI 自己實作存取控制,還是只是「不繞過」Postgres RLS /
Snowflake row access policy?

**答案:WrenAI 是自己在 logical plan 裡注入 Filter(內建強制),不是依賴底層 DB 的 RLS。**

證據就是 3.1 的 `build_rlac_filter`——它把 `WHERE tenant_id = @session_tenant_id`
加進 WrenAI 自己產的 SQL,再送給任何一種資料庫執行。所以即使底層是「沒有 RLS 功能
的資料庫」(如某些 DuckDB/檔案來源),WrenAI 這層仍會過濾。

**這兩種模式的安全保證差異(務必理解)**:

| | WrenAI 內建 RLAC(現況) | 依賴底層 DB RLS |
|---|---|---|
| 過濾發生在哪 | WrenAI 產 SQL 時注入 WHERE | DB 引擎執行時強制 |
| 繞過 WrenAI 直連 DB 會怎樣 | **失效**(WHERE 是 WrenAI 加的,直連就沒了) | 仍有效(DB 層強制) |
| 依賴什麼才安全 | **身份正確傳進 WrenAI + 沒人能繞過 WrenAI 直連** | DB 帳號與 policy 正確 |

**這是一把雙面刃**:WrenAI 內建 RLAC 讓「任何資料源都能有 row 級控制」,但它的安全性
建立在「所有查詢都必須經過 WrenAI 且 WrenAI 拿到正確身份」這個前提上。一旦有人能拿到
WrenAI 用的 DB credential 直連資料庫,RLAC 形同虛設——因為過濾條件不在 DB 那端。
→ 這直接連到 3.3 的問題。

---

## 3.3 身份傳遞鏈:最脆弱的環節 —— 預設 CLI 沒接身份 + 單一共用 credential

這是本章最重要、也最危險的發現。RLAC 的安全性 = 身份傳遞鏈的安全性。逐段檢查:

### (a) 引擎/SDK 層:有身份參數 ✅
`engine.py` 的 `dry_plan/query/dry_run` 都接受 `properties: dict | None`,一路傳到
`get_session_context(..., processed, ...)` 再進 Rust 引擎。所以**能力是通的**。

### (b) 預設 CLI 層:身份沒接上 ❌(關鍵缺口)
```python
# core/wren/src/wren/cli.py — query 指令
result = engine.query(sql, limit=limit)   # ← 沒有 properties!
```
`wren query` 指令**完全沒有傳 `properties`**,也沒有 `--property` / `--session` 這類
flag 讓你帶入使用者身份。意思是:**用預設 CLI 跑查詢時,RLAC 規則因為 session
property 缺失而不會套用**(`validate_rule` 對 required property 缺失會報錯、對 optional
會走 default)。

換言之:RLAC 引擎能力存在,但**預設的使用路徑沒有把使用者是誰告訴引擎**。要真正用到
RLAC,呼叫端(外部 agent 或自建服務)必須自己走 SDK、自己把 `properties` 帶進去。

> 註:CLI 有處理 connection file 裡的 `properties` envelope(`cli.py` 行 66-72),但那是
> **連線設定的封裝**(url/format 等),不是「每次查詢的使用者身份 session property」。
> 兩者是不同的東西,別混淆。

### (c) 連線層:單一共用 credential ❌(經典多租戶踩雷點)
```python
# engine.py:__init__
self.connection_info = data_source.get_connection_info(connection_info)
```
每個 `WrenEngine` 綁**一組** `connection_info`(host/user/password/role...),
預設從 `~/.wren/connection_info.json` 讀。所有查詢都用**這一組 DB credential** 執行。

這代表:
- 送到資料庫的查詢,是用**共用的 service account 權限**執行,不是「使用者本人的
  DB 權限」。
- 使用者之間的隔離**完全依賴 WrenAI 應用層的 RLAC 正確運作**(3.2 的內建過濾),
  而不是 DB 帳號權限。
- 若 RLAC 沒被套用(如 3.3-b 的預設 CLI 路徑),或身份被搞混,不同使用者就會用
  同一把權限看到彼此的資料。

**這正是你擔心的「連線池 / service account 共用 → 變相繞過存取控制」的教科書案例。**
WrenAI 的架構本身就是「單一 credential + 應用層過濾」,所以隔離的正確性 100% 壓在
「身份有沒有被每個查詢正確帶入 + RLAC 有沒有被套用」上。

### 身份傳遞鏈總結

```
使用者身份 (誰在問?)
   │  ❓ 由外部 agent / 自建服務負責取得並轉成 session property
   │      —— 預設 wren CLI 這一段是斷的
   ▼
engine.query(sql, properties={session_tenant_id: ...})   ✅ SDK 支援,但需自己帶
   ▼
Rust 引擎注入 WHERE tenant_id = @session_tenant_id       ✅ deterministic 強制
   ▼
連接器用「單一共用 credential」執行 SQL                    ⚠️ 非使用者本人 DB 權限
   ▼
資料庫(不知道真正的 end user 是誰,只認得 service account)
```

**判定(3.3)**:隔離鏈上有兩個高風險環節——(1) 身份到引擎這段,預設 CLI 沒接,
必須靠呼叫端自己實作且不能出錯;(2) DB 這端是共用權限,一旦繞過 WrenAI 直連就無防護。

---

## 3.4 如果不接身份會怎樣 / 實務補強

### WrenAI 沒有替你做的事
- 沒有內建的「使用者認證 / SSO / 身份來源」——WrenAI 不知道「誰在問」,它只接收
  你給它的 session property 值。**把『登入使用者』對應到正確的 session_tenant_id /
  session_user_id,是呼叫端的責任。**
- 沒有防止「session property 被偽造」的機制——如果外部 agent 可以任意設定
  `session_tenant_id`,使用者就能宣稱自己是別的租戶。property 的可信度 = 呼叫端
  身份驗證的可信度。

### 實務補強(建議部署形態)
1. **在 gateway / BFF 層做身份感知**:所有查詢必經一個受信任的後端服務,該服務:
   - 用 SSO/JWT 驗證使用者;
   - **由後端**(而非前端/agent)把已驗證的 identity 轉成 session property,
     呼叫 `engine.query(sql, properties={...})`;
   - 前端與 LLM **永遠拿不到**設定 session property 的能力。
2. **禁止繞過**:鎖死 DB,只有 WrenAI service account 能連;end user 無法直連
   資料庫(否則 3.2 的應用層 RLAC 會被繞過)。
3. **雙層防禦(縱深)**:除了 WrenAI RLAC,若底層 DB 支援(Postgres RLS /
   Snowflake row access policy),可額外對 service account 加 DB 層 policy,
   讓即使應用層漏接也有第二道。理想是「WrenAI RLAC + DB RLS」兩層都有。
4. **審計**:記錄每個查詢的 (end user, session properties, 展開後 SQL),
   以便事後稽核「誰用什麼身份查了什麼」。WrenAI 目前無內建 audit log
   (README「What's next」列為未來項目),需自建。

---

## 3.5 負責的模組(標註)

| 功能 | 檔案 |
|---|---|
| RLAC/CLAC 核心邏輯 | `core/wren-core/core/src/logical_plan/analyze/access_control.rs` |
| RLAC filter 注入 plan | `core/wren-core/core/src/logical_plan/analyze/plan.rs`(行 440/467) |
| CLAC 運算子 | `core/wren-core-base/src/mdl/cls.rs` |
| session property 型別 | `core/wren-core-base/src/mdl/manifest.rs` |
| 身份參數傳遞(Python) | `core/wren/src/wren/engine.py`、`mdl/__init__.py` |
| **預設 CLI(未接身份)** | `core/wren/src/wren/cli.py::query` |
| **連線/共用 credential** | `core/wren/src/wren/engine.py::__init__`、`connector/*.py` |
| 官方 RLAC 範例 | `core/wren-core/wren-example/examples/row-level-access-control.rs` |

---

## 3.6 動手驗證 🔬

```bash
# 1. 跑官方 RLAC Rust 範例,親眼看到 WHERE 被注入
cd core/wren-core && cargo run --example row-level-access-control
#   觀察:同一句 SELECT,帶不同 session_tenant_id 時回傳不同 rows

# 2. 驗證「預設 CLI 不套 RLAC」:對有 RLAC 的 MDL 用 wren query 查,
#    確認 required session property 缺失時的行為(報錯 or 未過濾)
wren query --sql "SELECT * FROM documents"   # 無 property → 觀察是否報錯/未過濾

# 3. 用 SDK 帶 properties 對照:
python -c "
from wren.engine import WrenEngine
e = WrenEngine(mdl, 'postgres', conn)
print(e.dry_plan('SELECT * FROM documents', properties={'session_tenant_id': \"'tenant-a'\"}))
"
#   檢查輸出 SQL 是否含 WHERE tenant_id = 'tenant-a'
```

---

**上一章** → [02 大量結果](02-large-result-handling.md)　|　**下一章** → [04 安全治理](04-security-governance.md)
