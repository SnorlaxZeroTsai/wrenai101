# WrenAI 101 — 從原始碼拆解 GenBI 引擎

> 目標:搞懂 WrenAI 的 **text2SQL、大量結果處理、資料存取隔離、安全治理** 四件事,
> 判斷它能不能用在「企業內部有敏感資料」的場景。
>
> **原則:以原始碼為準,不採信官方行銷式描述。** 每個結論都標註對應的檔案與行號。

驗證基準:2026-07 clone 的 `Canner/WrenAI`(commit 為當時 `main` HEAD),
Rust 引擎 + Python CLI/SDK。對照組為 `legacy/v1` 分支(Docker chat-first app)。

---

## ⚠️ 讀之前一定要先懂的一件事:WrenAI 現在是「兩套架構」

WrenAI 在 **2026-05-07 做了破壞性改版**。你在網路上看到的 90% 教學講的是「舊的那套」。

| | `main`(現行,本專案主軸) | `legacy/v1` 分支(已凍結) |
|---|---|---|
| 形態 | **agent-native**:Rust 語意引擎 + Python CLI/SDK + 瀏覽器端 GenBI dashboard | Docker chat-first BI app(`wren-ai-service/`) |
| text2SQL 由誰做 | **WrenAI 本身不含 LLM 服務**。由外部 agent(Claude、LangChain SDK)呼叫 `wren` CLI 產 SQL,WrenAI 只做 deterministic 的語意層轉換與治理 | 內建完整 RAG pipeline:retrieval → generation → correction → chart |
| 維護狀態 | 主線,持續開發 | **無新功能、無安全修補**(README 明載) |

→ 這個分裂直接決定了你四個問題的答案,每一章都會分辨「新 main」與「legacy/v1」。

證據:`main` 的 `README.md`(專案結構區塊)、`legacy/v1` 分支的
`wren-ai-service/src/pipelines/` 目錄。

---

## 章節目錄

| 章 | 主題 | 一句話結論 |
|---|---|---|
| [00](docs/00-two-architectures.md) | 兩套架構的分水嶺 | 不分辨 main/legacy 就會得到錯誤結論 |
| [01](docs/01-text2sql-deep-dive.md) | text2SQL 的真實分工邊界 | LLM 只產「對語意層的邏輯 SQL」,JOIN/方言/計算欄位由 Rust 引擎 deterministic 展開 |
| [02](docs/02-large-result-handling.md) | 大量查詢結果處理 | **幾乎無保護**:無預設 LIMIT、`fetchall()` 全量進記憶體、LLM 摘要是「塞爆再削」。企業硬缺口 |
| [03](docs/03-data-isolation.md) | 使用者資料存取隔離 | RLAC/CLAC 引擎層真強制,**但預設 CLI 沒接身份**、單一共用 credential → 繞過風險 |
| [04](docs/04-security-governance.md) | 安全性與可治理落地 | `policy.py` SQL firewall 是亮點,**但預設 `strict_mode=False`(關閉)** |
| [05](docs/05-enterprise-verdict.md) | 企業採用總評 | 語意層可信、執行層需外部補強;附信任度總表與補強清單 |

深挖優先序(依「值不值得信任」):**第 3 章 > 第 2 章 > 第 4 章 > 第 1 章**。
理由見各章開頭。

---

## 每個結論的驗證方式

- 📖 **讀原始碼即可確認** — 本專案大部分結論屬此類,已在文中附檔案:行號。
- 🔬 **需 clone/跑起來實測** — 標記於各章「動手驗證」小節,附可複製指令。

想自己複現:

```bash
git clone https://github.com/Canner/WrenAI.git
# main = 現行 agent-native 架構
# git checkout legacy/v1 = 舊 Docker RAG app(對照組)
```

本專案不把 clone 的原始碼納入 git(見 `.gitignore`),請自行 clone 對照。

---

## 給趕時間的人(TL;DR)

WrenAI 的價值在 **deterministic 語意層**:MDL 把業務語意編譯進 SQL,
JOIN/計算/方言由 Rust 引擎處理,LLM 只需產「邏輯 SQL」,這確實能壓低
text2SQL 常見錯誤(第 1 章)。RLAC/CLAC 是引擎層真強制,不是靠 LLM 自律(第 3 章)。

但**執行層的企業級護欄大多預設關閉或缺席**:SQL firewall 預設 off、
無預設 row limit、身份未接進預設 CLI、單一共用 DB credential。
要用在敏感資料場景,必須在 gateway/DB 層外掛身份感知存取控制與資源護欄(第 5 章)。
