# 第 3 章:使用者資料存取隔離

> 深挖優先序:**第 2**(僅次於第 6 章對照組)。這是「使用者操作到不屬於他的資料」這個具體風險的核心,
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

### Column-Level Access Control(CLAC)—— 2026-07-09 起是「雙軌」行為

CLAC 在 `validate_clac_rule`(`access_control.rs` 行 534)判斷某欄位對當前 session
是否可見:規則綁一個 session property,用 `clac.eval(value)` 比對
(支援 `Equals/NotEquals/GreaterThan/...`,見 `wren-core-base/src/mdl/cls.rs`)。
還會遞迴檢查 calculated field 依賴的來源欄位(`required_fields_map`),
避免「用計算欄位繞過欄位遮蔽」。

**⚠️ 修訂(2026-07-09,commit `a8a7519` / #2449)**:本書初版寫「不通過 → 該欄位
被擋」,這句現在只對一半。不通過之後發生什麼,取決於欄位**怎麼被引用**:

| 引用方式 | CLS 不通過時的行為 | 證據 |
|---|---|---|
| **明確引用**(SELECT list、WHERE、GROUP BY、JOIN ON 任何位置點名該欄位) | **整句查詢被拒**,回 `Access denied to column "model"."col": violates access control rule "..."` | `plan.rs:166-195`(named required fields 路徑) |
| **隱式/wildcard 展開**(`SELECT *`、`SELECT e.*`、`count(*)`、帶 table alias 的 model scan) | **該欄位被靜默剪除**,查詢照常成功,結果就是少這一欄 | `plan.rs:1049-1067`(展開迴圈呼叫 `validate_clac_rule`,不通過就 `continue`);測試 `mdl/mod.rs::test_clac_unreferenced_column_pruned_not_denied` |

改版動機是修 bug:改版前,`count(*)` 或帶 alias 的查詢即使**從未碰**被保護欄位,
也會因為內部 wildcard 展開觸發 CLS 而整句被拒——現在改成貼近 `SELECT *` 直覺語意
(給你「你看得到的所有欄位」)。

**治理視角的雙面解讀(教材重點)**:

- **fail-loud(明確引用 → 拒絕)**:使用者被明確告知「你沒有權限」。資訊洩漏面
  來看,錯誤訊息本身確認了該欄位存在——但在 MDL 場景欄位名單本來就在 schema
  context 裡,不算新增洩漏。
- **fail-silent(wildcard → 剪除)**:查詢成功但**使用者不會被告知有欄位被藏了**。
  對「不同角色看到不同欄寬」的多租戶報表這是理想語意。值得注意的是 DB 界
  對此**並無單一慣例**:Postgres column privilege 下 `SELECT *` 是整句失敗
  (permission denied,絕不剪欄);Snowflake masking policy 是遮值不藏欄;
  WrenAI 選了第三種——藏欄,貼近「給你你看得到的所有欄位」的直覺語意。
  但對「下游程式依賴欄位存在」的整合場景,靜默剪除會讓 schema 隨身份漂移,
  除錯時很難想到是 CLS 在作用。審計上也要注意:沒有任何 log 記錄
  「這次查詢剪掉了哪些欄」(本章 3.4 的審計缺口再 +1)。

證據:`core/wren-core/core/src/logical_plan/analyze/access_control.rs`(RLAC/CLAC 邏輯)、
`core/wren-core-base/src/mdl/cls.rs`(CLAC 運算子)、`plan.rs`(注入點)。

值得加碼的一個細節:`plan.rs:979-996` 有一道防禦性檢查——若 DataFusion 的 plan
遍歷過程把已注入的 `rlac_filter` 弄丟,引擎會直接擲 `internal_err` 讓查詢失敗,
而不是靜默退化成「無過濾」。這是「寧可掛掉也不洩漏」的 fail-closed 設計,
進一步支持「引擎層真強制」的判定。

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

### (a) 引擎層:有身份參數 ✅(但 agent SDK 也沒把它接出來 ⚠️)
`engine.py` 的 `dry_plan/query/dry_run` 都接受 `properties: dict | None`,一路傳到
`get_session_context(..., processed, ...)` 再進 Rust 引擎。所以**能力是通的**。

但注意(2026-07 核驗):**官方 agent SDK 同樣沒接**——`wren-langchain` 的
`WrenToolkit.query(sql, limit)` 與 LLM-facing 的 `wren_query` 工具簽名裡
都沒有 `properties`(`sdk/wren-langchain/src/wren_langchain/_toolkit.py:61`)。
這其實是正確的安全設計:session property 若暴露成 LLM 可填的工具參數,
等於讓 LLM(可被 prompt injection 操縱)自報身份。正確接法只有一種:
由受信任的後端在建 engine/toolkit 時綁定,LLM 摸不到(見 3.4)。

### (b) 預設 CLI 層:身份沒接上 ❌(關鍵缺口)
```python
# core/wren/src/wren/cli.py — query 指令
result = engine.query(sql, limit=limit)   # ← 沒有 properties!
```
`wren query` 指令**完全沒有傳 `properties`**,也沒有 `--property` / `--session` 這類
flag 讓你帶入使用者身份。那 session property 缺失時 RLAC 會怎樣?
`validate_rule`(`access_control.rs:494`)其實分**三種行為**,安全意涵天差地遠:

| 規則的 property 宣告 | property 缺失時 | 安全意涵 |
|---|---|---|
| `required` | **整句查詢報錯**(`plan_err!`) | fail-closed,安全——查不到任何東西 |
| `optional` + 有 `default_expr` | 規則照常套用(代入 default 值) | 看 default 設得對不對 |
| `optional` + 無 default | **規則被靜默跳過 → 資料未過濾放行** | 🔴 真正的洩漏路徑 |

所以「預設 CLI 沒接身份」的實際後果取決於 MDL 作者怎麼宣告規則:全用 `required`
的話,預設 CLI 對受控模型**整句失敗**(fail-closed,煩人但安全);一旦有規則
是「optional 無 default」,預設 CLI 就會**無過濾地回傳全部資料**。教訓:
**多租戶隔離規則一律宣告 `required`**,把 optional 留給「錦上添花」的過濾。

換言之:RLAC 引擎能力存在,但**預設的使用路徑沒有把使用者是誰告訴引擎**。要真正用到
RLAC,呼叫端(外部 agent 或自建服務)必須自己走 SDK、自己把 `properties` 帶進去。

> 註:CLI 有處理 connection file 裡的 `properties` envelope(`cli.py` 行 66-72),但那是
> **連線設定的封裝**(url/format 等),不是「每次查詢的使用者身份 session property」。
> 兩者是不同的東西,別混淆。

### (c) 連線層:單一共用 credential ❌(經典多租戶踩雷點)
```python
# engine.py:__init__(行 77)
self.connection_info = data_source.get_connection_info(connection_info)
```
每個 `WrenEngine` 綁**一組** `connection_info`(host/user/password/role...)。
所有查詢都用**這一組 DB credential** 執行。

(2026-07 註:連線設定的主流路徑已從 `~/.wren/connection_info.json` 改成
**named profiles**(`~/.wren/profiles.yml`,secret 用環境變數展開,
`wren profile add/switch`);舊 json 路徑仍在(`cli.py:17`)但已屬 legacy。
**身份粒度不變**:profile 是 per-database 的連線身份,不是 per-user——
換了設定格式,共用 credential 的本質沒變。)

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

### 這個斷裂是商業模式設計,不是疏忽(2026-07 補證)

官方 `docs/core/concepts/oss_vs_commercial.md` 的能力對照表把界線劃得很明白:

| Capability | Open source | Commercial |
|---|:---:|:---:|
| Access control **defined in MDL**(RLAC/CLAC) | ✅ | ✅ |
| Accounts, roles, multi-user | ❌ | ✅ |
| SSO, LDAP, SCIM provisioning | ❌ | ✅ |
| **RLS/CLS per user, session properties, audit log** | ❌ | ✅ |

讀懂這張表:OSS 給你**引擎能力**(RLAC/CLAC 規則定義與強制),但「把真實使用者
身份接上 session property」這一段——帳號、SSO、per-user 的 RLS/CLS、audit log——
是**商業版的賣點**。所以預設 CLI 不接身份、SDK 工具不暴露 properties,
不是還沒做完,是**開源/商業的分界線刻意劃在這裡**。

對評估的意涵:自建 gateway 補身份鏈(見 3.4)= 自己重做商業版的核心加值;
這條路技術上可行(SDK 的 `properties` 參數是通的),但要有「這是在自建
商業版功能」的認知來估工作量,而不是「補個小缺口」。

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

# 1b. 驗證 CLAC 雙軌行為(a8a7519 起,見 §3.1)
cd core/wren-core && cargo test test_clac_unreferenced_column_pruned_not_denied
#   或自己對有 CLS 規則的 MDL 試兩句:
#   SELECT * FROM employees          → 成功,結果少了被保護的欄(靜默剪除)
#   SELECT salary FROM employees     → Access denied(明確引用被拒)

# 2. 驗證「預設 CLI 沒接身份」的三種後果(對應 3.3(b) 的表):
#    對有 RLAC 的 MDL 用 wren query 查(CLI 不會帶任何 session property)
wren query --sql "SELECT * FROM documents"
#    規則 required           → 預期整句報錯 "session property ... is required"
#    規則 optional 有 default → 預期套 default 值過濾
#    規則 optional 無 default → 預期【無過濾回傳全量】← 重點驗這個洩漏路徑

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
