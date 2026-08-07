# 第 0 章:兩套架構的分水嶺

> **Historical deep dive**：本章保留舊 repository 研究，用來辨識網路資料談的是
> current `main` 還是 frozen `legacy/v1`。第一次閱讀請先看
> [fundamentals/01-what-is-wrenai](../fundamentals/01-what-is-wrenai.md)；current
> architecture 以 `9a0f032` 與 [`UPSTREAM_STATE.md`](../../UPSTREAM_STATE.md) 為準。
>
> 為什麼這章要放最前面:因為你的四個問題(text2SQL、大量結果、資料隔離、治理)
> 在「新 main」和「legacy/v1」裡答案完全不同。分不清楚,結論就會錯。

---

## 0.1 事件:2026-05-07 的破壞性改版

WrenAI 官方 README 開頭有一則公告(2026-05-07):

> Wren Engine has merged into this repo under `core/`. The previous WrenAI GenBI app
> (the Docker-based chat-first BI product) is preserved on the `legacy/v1` branch
> (tag `v1-final`) and is now **Wren GenBI Classic**.

翻成白話:

- 原本 WrenAI = 一個 Docker 起來的聊天式 BI 產品,裡面有一包 Python 的 AI 服務
  (`wren-ai-service`),負責「使用者打字問問題 → RAG → LLM 生 SQL → 執行 → 畫圖」。
- 改版後,`main` 分支變成 **agent-native**:核心只剩「Rust 語意引擎 + Python CLI/SDK」,
  **不再內建 LLM 生成服務**。改由外部 agent(例如 Claude Code、LangChain agent)
  透過 CLI/SDK 呼叫 WrenAI 做 deterministic 的語意層工作。
- 舊那套整包移到 `legacy/v1` 分支,**明載不再有新功能、不再有安全修補**。

證據:
- `main` `README.md` 的公告區塊與「A note on the "GenBI" name」段落。
- `main` 的專案結構只有 `core/`(Rust + CLI)、`sdk/`、`skills/`,**沒有 `wren-ai-service/`**。
- `legacy/v1` 分支才有 `wren-ai-service/src/pipelines/{retrieval,generation}/`。

---

## 0.2 兩套架構的職責對照

### `main`(現行)

```
外部 agent (Claude / LangChain)   ← LLM 在這裡,不屬於 WrenAI
        │  自然語言 → 邏輯 SQL
        ▼
core/wren/  (Python CLI/SDK, PyPI: wrenai)
        │  ├─ memory/          schema context 供應 + NL→SQL 記憶(給 agent 拉)
        │  ├─ policy.py        SQL firewall(選配,預設關)
        │  ├─ engine.py        planning + 執行協調
        │  └─ connector/*.py   22+ 資料源連線與執行
        ▼
core/wren-core*  (Rust, DataFusion)
           ├─ MDL 語意展開(relationship→JOIN、calculated column、方言)
           └─ RLAC / CLAC 存取控制(row/column 級,deterministic 強制,第 3 章)
        ▼
   使用者的資料庫(Postgres / BigQuery / Snowflake / …)
```

關鍵:**LLM 不在 WrenAI 裡**。WrenAI 在 `main` 的定位是「給 agent 用的、
可信任的 deterministic 語意 + 治理層」。text2SQL 的「文字→SQL」那一步,
是外部 agent 拿著 WrenAI 提供的 MDL context 自己做的。

### `legacy/v1`(已凍結)

```
使用者在 Web UI 打字
        ▼
wren-ai-service/ (Python, Haystack pipelines)
   retrieval/    ─ 從 MDL 建 DDL、embedding 檢索相關表、找歷史相似問題
   generation/   ─ sql_generation → sql_correction → sql_answer → chart_generation
        ▼
   wren-engine (舊版語意引擎)
        ▼
   資料庫
```

這套才是多數教學講的「WrenAI 怎麼用 RAG 做 text2SQL」。它仍是理解生成邏輯的
好參考,但**不要當成現行架構**。

---

## 0.3 這對你四個問題的影響(本專案的取材策略)

| 你的問題 | 主要看哪套 | 原因 |
|---|---|---|
| text2SQL 怎麼做 | **main**(context 供應鏈 + 語意層)+ legacy(內建生成管線對照) | main 不含 LLM,但有自己的 context 組裝機制(`wren memory`/`ask`/skills,第 1 章 §1.2);legacy 的 RAG 管線降為對照組 |
| 大量結果處理 | main(connector + SDK 護欄)+ legacy(LLM 摘要) | 執行與 SDK 護欄在 main;「rows 餵 LLM 的內建管線」只在 legacy |
| 資料存取隔離 | **main**(RLAC/CLAC 在新 Rust 引擎) | 這是 main 才有的能力 |
| 安全治理 | **main**(policy.py + RLAC/CLAC) | 治理原語是 main 的重點 |

**本專案主軸 = `main`**,legacy/v1 僅在「生成邏輯」與「LLM 摘要」兩處當對照。
理由:main 是你未來會實際評估與部署的東西;legacy 已無安全修補,拿它當企業評估
基準沒有意義。

---

## 0.4 一個常見誤解先破除

> 「WrenAI = text-to-SQL 工具」

錯。在 `main` 的定位裡,WrenAI **不做** text-to-SQL 的「text」那一半——那是 agent/LLM 的事。
WrenAI 做的是:

1. 提供 LLM 需要的**語意 context**(MDL,而非原始 schema);
2. 把 LLM 產出的「邏輯 SQL」**deterministic 展開**成真正能跑、方言正確的 SQL;
3. 在展開與執行過程中套用**治理**(存取控制;SQL firewall 選配、預設關;
   row limit 僅 SDK 工具路徑有預設,見第 2 章)。

官方自己也強調 "Not just text-to-SQL"(README)。理解這點,後面每一章才讀得通。

---

**下一章** → [01 text2SQL 的真實分工邊界](text2sql.md)
