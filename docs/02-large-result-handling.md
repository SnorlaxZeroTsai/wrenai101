# 第 2 章:大量查詢結果的處理

> 深挖優先序:**第 2**(僅次於資料隔離)。這章缺口最多,也是文件最避而不談的地方。
> 一句話結論:**WrenAI 對「大量結果」幾乎沒有內建保護**,企業場景必須外部補強。

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

# core/wren/src/wren/connector/postgres.py
def query(self, sql, limit=None):
    if limit is not None:                            # ← 只有非 None 才包 LIMIT
        sql = f"SELECT * FROM ({sql}) AS _sub LIMIT {limit}"
    with self.connection.cursor() as cursor:
        cursor.execute(sql)
        return _build_pg_arrow_table(cursor)         # 見 2.2
```

- LIMIT 是**外層包裹**(`SELECT * FROM (<user sql>) AS _sub LIMIT n`),不是改寫內層,
  所以 DB 仍可能先做完整內層計算再截斷——**limit 保護的是「回傳列數」,不必然
  保護「掃描量」**。
- `core/wren-core-py/src/context.rs::pushdown_limit`(行 271)有一個「把 limit 下推到
  查詢內層」的能力,但那是 **opt-in 的 API**,不是預設在每個查詢上自動套用。

**判定:這是「可調整、需呼叫端自己決定」的機制,不是預設護欄。** 一個外部 agent
若沒傳 limit,一句自然語言就能觸發全表回傳。→ 企業缺口 #1。

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
rows 餵給 LLM。這反而更危險:若 agent 實作者天真地把 `wren query` 的 Arrow table
全丟進 prompt,原始資料列就直接送到 LLM API(見第 4 章資料外洩)。WrenAI 沒有在
這個邊界上強制任何保護。

→ 企業缺口 #3:摘要走「全量撈取 → 尾端截斷」,非 DB 端彙總;且原始 rows 會進 prompt。

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
| 1 | 無預設 row limit | `limit` 預設 `None`,不傳就不限 | 在 gateway/SDK 包一層**強制預設 LIMIT**;或用 `pushdown_limit` 對每個查詢下推上限 |
| 2 | 無 streaming/分頁 | `fetchall()` 全量進記憶體 | 改用 server-side cursor + `fetchmany` 分批;或在 gateway 做分頁 API |
| 3 | 摘要塞全量 rows、尾端截斷 | legacy `preprocess_sql_data` 撈全量再砍尾 | 摘要一律走**彙總 SQL**(GROUP BY / MDL metrics),只把彙總列給 LLM;或改成有代表性的抽樣 |
| 4 | 圖表可能前端吞全量 | 未見後端 downsampling | 圖表查詢強制彙總;後端 downsampling 後再送前端 |
| 5 | timeout 不一致 | 僅部分連接器支援 | 統一在連線層設 statement timeout,防長查詢佔用資源 |

**總評**:WrenAI 在「大量結果」這塊基本上把責任推給呼叫端(agent / 部署者)。
語意層(MDL metrics/cubes)提供了「做對彙總」的工具,但**沒有任何預設護欄
強制大結果被安全處理**。企業採用前,這是必須外掛的一層。

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

**上一章** → [01 text2SQL](01-text2sql-deep-dive.md)　|　**下一章** → [03 資料存取隔離](03-data-isolation.md)
