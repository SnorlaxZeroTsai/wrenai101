# 第 2 章:大量查詢結果的處理

> **Snapshot note**：本章來自 `a8a7519`。`WrenEngine.query` 對 limit 的 handoff 已
> 在 `9a0f032` 用
> [`experiments/05-result-limits`](../../experiments/05-result-limits/) 重驗；
> SDK cap、connector fetch strategy、前端與 legacy behavior 在作新採用判斷前仍需
> 逐 path 重新驗證。
>
> 深挖優先序:**第 4**。這章缺口多,也是文件最避而不談的地方。
>
> **2026-07-09 修訂**:原版結論「幾乎沒有內建保護」需要分層修正——
> **engine/CLI 層確實無護欄(不變),但 SDK 層(wren-langchain / wren-pydantic)
> 其實有紮實的預設保護**(limit=100、硬上限 1000、16KB content cap)。
> 「你的 agent 走哪條路徑進來」決定了有沒有防護,這對企業評估是關鍵差異。
> 見新增的 §2.1b。

四個子問題:(1) 會不會自動加 LIMIT?(2) 資料怎麼從 DB 到前端?
(3) 大量結果會不會塞進 LLM?(4) 圖表在大資料集下可行嗎?

---

## 2.1 SQL 會自動加 LIMIT 嗎?→ **不會有預設上限**,只有「顯式傳入才加」

**結論:沒有寫死的預設 row 上限。** `LIMIT` 只有在呼叫端明確傳 `limit` 時才會被加上,
預設是 `None`(無限制)。

證據鏈:

```python
# core/wren/src/wren/cli.py — query 指令
def query(sql, ..., limit: LimitOpt = None, ...):   # 預設 None
    result = engine.query(sql, limit=limit)         # 沒傳就是 None

# core/wren/src/wren/engine.py
def query(self, sql, limit=None, properties=None):
    dialect_sql = self.dry_plan(sql, properties)
    return connector.query(dialect_sql, limit)      # limit 原樣往下傳

# core/wren/src/wren/connector/postgres.py(行 268-273)
def query(self, sql, limit=None):
    if limit is not None:                            # ← 只有非 None 才包 LIMIT
        sql = f"SELECT * FROM ({_strip_trailing_semicolon(sql)}) AS _sub LIMIT {limit}"
    with self.connection.cursor() as cursor:
        cursor.execute(sql)
        return _build_pg_arrow_table(cursor)         # 見 2.2
```

(2026-07 註:`_strip_trailing_semicolon` 是 #2407 起加的分號剝除,postgres 等
10 個連接器比照——修的是「SQL 尾端帶 `;` 時外層包裹會產生語法錯誤」,
不改變「無預設上限」的結論。)

- LIMIT 是**外層包裹**(`SELECT * FROM (<user sql>) AS _sub LIMIT n`),不是改寫內層,
  所以 DB 仍可能先做完整內層計算再截斷——**limit 保護的是「回傳列數」,不必然
  保護「掃描量」**。
- `core/wren-core-py/src/context.rs::pushdown_limit`(行 271)有一個「把 limit 下推到
  查詢內層」的能力,但那是 **opt-in 的 API**,不是預設在每個查詢上自動套用。

**判定:這是「可調整、需呼叫端自己決定」的機制,不是預設護欄。** 一個外部 agent
若沒傳 limit,一句自然語言就能觸發全表回傳。→ 企業缺口 #1(但先看 §2.1b:
走官方 SDK 的 agent 不受此缺口影響)。

---

## 2.1b 例外:SDK 層有真護欄(2026-07 補寫,修正原版結論)

原版說「幾乎無保護」——對 engine/CLI 層成立,但漏看了官方 agent SDK。
`wren-langchain` 和 `wren-pydantic` 給 LLM 的 `wren_query` 工具有預設防護
(前兩道兩個 SDK 共通,第三道 wren-langchain 獨有):

```python
# sdk/wren-langchain/src/wren_langchain/_tools.py(limit/cap 部分 wren-pydantic 同款)
MAX_QUERY_ROWS = 1000        # 硬上限

@tool("wren_query")
def wren_query(sql: str, limit: int = 100) -> dict:   # ← 預設 100,不是 None!
    """... Default limit is 100 rows; increase only when you need more.
    Hard cap is 1000 rows — beyond that, aggregate in SQL instead."""
    if limit < 1 or limit > MAX_QUERY_ROWS:
        # 拒絕,並回訊息教 LLM「要更多列就改用聚合 SQL」
```

1. **預設 `limit=100`**:LLM 不指定就是 100 列,不是全表。
2. **硬上限 `MAX_QUERY_ROWS=1000`**:LLM 打字錯誤或幻覺出一個超大 limit 時直接拒絕,
   錯誤訊息明確引導「Aggregate in SQL if you need more rows」——把 LLM 推向
   DB 端彙總,正是 2.3 說的正確方向。原始碼註解寫明威脅模型:
   「a runaway `limit` value (typo, hallucinated huge number) would still balloon
   memory before that cap fires」。
3. **回傳內容 16KB cap(僅 wren-langchain)**(`_format.py`,`CONTENT_CAP_BYTES`):
   餵給 LLM 的 rendered rows 超過 16KB 就截斷,並附 `content_truncated=True` +
   「showed N of M rows due to size cap」警告——**截斷是顯式告知的**,
   LLM 知道自己沒看到全部(對照 legacy 的靜默砍尾,見 2.3,這是明確的進步)。
   wren-pydantic **沒有**這道:它的 payload 只靠 1000 列硬上限管住,
   另以 `truncated` 布林旗標告知結果被 limit 截斷(`_models.py`)。

**兩個必須看清楚的防護邊界**:

- **16KB cap 只管 `content` 欄位**:wren-langchain 工具回傳的 envelope 裡,
  `content`(渲染文字)被 16KB cap 管住,但 `data.rows = table.to_pylist()`
  ——最多 1000 列的原始資料——**不受 size cap**(原始碼註解自己承認
  「data.rows materializes every row」)。LangChain 預設把整個 dict 序列化進
  ToolMessage,所以實際進 prompt 的量,**真正的通用上限是 1000 列,不是 16KB**。
- **護欄只綁 LLM-facing 工具**:同一個 SDK 的 Python 直接 API
  (`toolkit.query(sql, limit=None)`)**刻意不設上限**——原始碼註解:
  「Direct API keeps no cap on purpose; that's a Python-programmer surface.」

修正後的分層結論:

| 進入路徑 | 預設 limit | 硬上限 | 進 LLM 的內容截斷 |
|---|---|---|---|
| `wren query`(CLI) | ❌ 無 | ❌ 無 | —(印 stdout) |
| `engine.query()` / `toolkit.query()`(Python API) | ❌ 無 | ❌ 無 | — |
| **SDK 工具 `wren_query`(LLM-facing)** | ✅ 100 | ✅ 1000 | 🟡 langchain:content 16KB+顯式警告(data.rows 不 cap);pydantic:僅 truncated 旗標 |
| legacy `sql_answer` 管線 | ❌ 撈全量 | ❌ | ⚠️ 靜默砍尾(見 2.3) |

**企業意涵**:自建 agent 時,走官方 SDK 工具就繼承了合理的預設;自己包 CLI 或
直接呼叫 engine API,護欄要自己補。WrenAI 的護欄哲學是「守 LLM 這個不可信輸入源,
不守工程師」——理解這個設計意圖,才知道哪些路徑要自己看緊。

### timeout 呢?
- **BigQuery**:支援 `job_timeout_ms`(connection_info 帶入)。
- **ClickHouse**:支援 `statement_timeout` → `max_execution_time`。
- **Postgres / MySQL 等多數連接器**:query 路徑沒有預設 statement timeout;
  只在例外處理捕捉 `TimeoutError`/`QueryCanceled`,代表 timeout 得靠底層連線設定,
  WrenAI 層沒有統一預設。

證據:`core/wren/src/wren/connector/{bigquery,clickhouse,postgres,athena}.py`。

---

## 2.2 DB → 前端的資料路徑:**整批載入(fetchall)**,非串流、非分頁

**結論:預設是「一次撈完、全量進記憶體」。**

```python
# postgres.py
with self.connection.cursor() as cursor:
    cursor.execute(sql)
    return _build_pg_arrow_table(cursor)   # 內部 cursor.fetchall()（行 139）

# bigquery.py
return self.connection.query(sql).result(max_results=limit).to_arrow()
```

- Postgres 連接器用 `cursor.fetchall()` 把整個結果集拉進記憶體再轉 Arrow table。
  **沒有 server-side cursor、沒有 `fetchmany` 分批、沒有 streaming。**
- 回傳型別是 `pyarrow.Table`(整張表在記憶體),不是 iterator/stream。

**記憶體與延遲影響**:
- 若沒帶 limit 且查詢回傳百萬列,這些列會**全部進 WrenAI 行程的記憶體**再序列化。
  大結果集 = 記憶體暴增 + 首位元組延遲高(要等 DB 全部算完 + 全部傳完)。
- 對「瀏覽器端 GenBI dashboard」而言,資料還要再送到前端;沒有後端分頁機制代表
  前端可能得吞下全量資料(見 2.4)。

→ 企業缺口 #2:無 streaming/pagination,大結果集在記憶體與延遲上都不友善。

---

## 2.3 大量結果會被塞進 LLM 嗎?→ 會(legacy),而且是「塞爆再削」而非「DB 端彙總」

這正是你擔心的情境:使用者問完數據後接著說「幫我總結這些資料」。

**在 `legacy/v1` 的 `sql_answer` 管線,答案是:把查詢回傳的 rows 直接放進 prompt。**

```jinja
{# wren-ai-service/src/pipelines/generation/sql_answer.py 的 prompt #}
rows: {{ sql_data.data }}     ← 原始資料列直接注入 prompt
```

那怎麼避免塞爆 context?看 `preprocess_sql_data.py` 的實際做法:

```python
# 先算整包資料的 token 數
_token_count = len(encoding.encode(str(sql_data)))
while _token_count > context_window_size:
    # 每次從「尾端」砍 50 列,重算 token,直到低於 context window
    sql_data["data"] = reduce_data_size(data)   # data[:len-50]
    _token_count = len(encoding.encode(str(sql_data)))
    if iteration > 1000: break                  # 防無限迴圈
```

這揭露幾件重要的事:

1. **它是先撈全量 rows 再事後削減**,不是「先在 DB 層 aggregation、只把彙總結果給 LLM」。
   你希望看到的「DB 端 pre-aggregation」**並不存在於這條摘要路徑**。
2. **削減方式是「從尾端砍」(`data[:elements_to_keep]`)**,不是抽樣、不是彙總。
   意思是 LLM 只看得到「前 N 列」,尾端資料被無聲丟棄——對「總結這些資料」這種
   需求會產生**偏誤的摘要**(只反映前段資料),而且 LLM 不會知道資料被截斷了。
3. 回傳 `num_rows_used_in_llm` 告訴上層「實際用了幾列」,算是有留下可觀測性,
   但終端使用者未必看得到。

證據:`legacy/v1` `wren-ai-service/src/pipelines/{generation/sql_answer.py,
retrieval/preprocess_sql_data.py}`。

**對 `main` 的意涵**:main 沒有內建這條摘要管線——是**外部 agent 自己**決定要不要把
rows 餵給 LLM。風險分路徑(呼應 §2.1b):走 SDK 工具的 agent,進 prompt 的內容
被 16KB cap + 顯式截斷警告管住;自己包 CLI/engine API 的 agent 若天真地把
Arrow table 全丟進 prompt,原始資料列就直接送到 LLM API(見第 4 章資料外洩)——
這條邊界 WrenAI 不替你守。

→ 企業缺口 #3(範圍縮小):摘要走「全量撈取 → 尾端截斷」是 legacy 行為;
main 的 SDK 路徑有顯式截斷,但「rows 該不該進 prompt」這個 DLP 決策仍無人強制。

**正確的企業做法應該是**:讓 agent 產生「彙總型 SQL」(GROUP BY / 聚合),在 DB 端算完
只回傳彙總列給 LLM;而不是撈明細再讓 LLM 自己數。WrenAI 的 MDL metrics/cubes 其實
支援這種彙總定義(第 1 章),但「摘要時要走彙總路徑」這件事沒有被強制,靠 agent 自律。

---

## 2.4 圖表 / dashboard 在大資料集下:瀏覽器端渲染,大企業資料集有隱憂

- `main` 的 GenBI dashboard 是 **browser-side app**,由 `wren-core-wasm`(WebAssembly)
  驅動(README「What's Included」)。
- legacy 的圖表走 `chart_generation.py`,產出 **Vega-Lite** spec
  (`utils/vega-lite-schema-v5.json`)。Vega-Lite 是在前端渲染的宣告式圖表。

**風險**:若後端沒有先做 downsampling/aggregation,而是把全量資料交給
瀏覽器端的 wasm/Vega-Lite 渲染,那麼:
- 資料量大時瀏覽器記憶體/渲染會撐不住(Vega-Lite 對「數萬點以上」本就吃力);
- 對大型企業資料集(動輒百萬列)不可行,除非查詢本身已是彙總結果。

原始碼中**未見**後端對圖表資料做強制 downsampling 的機制。實務上要靠「圖表對應的
查詢本來就是彙總 SQL」來間接控制資料量。→ 企業缺口 #4(需實測確認 wasm 端上限)。

---

## 2.5 缺口清單與企業補強建議

| # | 缺口 | 現況(原始碼) | 補強建議 |
|---|---|---|---|
| 1 | CLI/直接 API 無預設 row limit | `limit` 預設 `None`;**SDK 工具路徑已有 100/1000 護欄(§2.1b)** | 非 SDK 路徑在 gateway 包一層**強制預設 LIMIT**;或用 `pushdown_limit` 下推上限 |
| 2 | 無 streaming/分頁 | `fetchall()` 全量進記憶體(所有路徑,含 SDK——limit 先在 SQL 層生效,但 1000 列內仍是整批) | 改用 server-side cursor + `fetchmany` 分批;或在 gateway 做分頁 API |
| 3 | 摘要塞全量 rows、尾端截斷 | legacy `preprocess_sql_data` 撈全量再砍尾;main SDK 有 16KB 顯式截斷 | 摘要一律走**彙總 SQL**(GROUP BY / MDL metrics),只把彙總列給 LLM;或改成有代表性的抽樣 |
| 4 | 圖表可能前端吞全量 | 未見後端 downsampling | 圖表查詢強制彙總;後端 downsampling 後再送前端 |
| 5 | timeout 不一致 | 僅部分連接器支援 | 統一在連線層設 statement timeout,防長查詢佔用資源 |

**總評(2026-07 修訂)**:WrenAI 的護欄哲學是「**守 LLM,不守工程師**」——
LLM 可觸及的表面(SDK 工具)有紮實預設(limit=100、cap 1000、16KB 顯式截斷),
LLM 之外的表面(CLI、Python API)刻意不設限。企業評估時的問題從「有沒有保護」
變成「**你的部署把哪些表面暴露給誰**」:agent 全走 SDK 工具 → 缺口 #1/#3 大致已被涵蓋;有任何路徑繞過 SDK 工具直呼
CLI/API → 該路徑的 limit/timeout/DLP 要自己補。streaming(#2)與 timeout(#5)則是所有路徑共同的缺口。

---

## 2.6 動手驗證 🔬

```bash
# 1. 證明無預設 LIMIT:對一張大表不帶 --limit 查詢,觀察是否全量回傳
wren query --sql "SELECT * FROM large_table"        # 預期:無 LIMIT,全量撈
wren query --sql "SELECT * FROM large_table" -l 100  # 對照:外層包 LIMIT 100

# 2. 觀察記憶體:對大結果集查詢時監看 wren 行程 RSS,確認是否整批進記憶體
/usr/bin/time -v wren query --sql "SELECT * FROM large_table"

# 3. (legacy) 驗證摘要截斷:餵一個回傳數千列的查詢給 sql_answer,
#    檢查 log 的 "Reducing data size by 50 rows" 與 num_rows_used_in_llm
```

---

**上一章** → [01 text2SQL](text2sql.md)　|　**下一章** → [03 資料存取隔離](data-isolation.md)
