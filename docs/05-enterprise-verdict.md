# 第 5 章:企業採用總評 —— 能不能用在有敏感資料的內部場景

> 本章把前四章的原始碼發現收斂成一個決策。判準:**這個機制值不值得信任、
> 能不能用在企業內部有敏感資料的場景。** 不美化已知限制。

---

## 5.1 一句話定位

**WrenAI 是一個「可信任的 deterministic 語意層 + 一組治理原語」,不是「開箱即用的
企業級治理平台」。** 它把 text2SQL 最容易錯、最危險的部分(JOIN/計算/存取控制)
做成引擎層 deterministic 強制,這部分值得信任;但執行層的企業級護欄(身份注入、
結果保護、審計、rate limit)大多預設關閉或缺席,必須外部補強後才適合敏感資料場景。

---

## 5.2 信任度總表(逐機制)

| 機制 | 內建強度 | 成熟度 | 預設狀態 | 敏感資料場景可信嗎 |
|---|---|---|---|---|
| MDL 語意層(降 text2SQL 錯誤) | 強(deterministic 展開) | 高 | 啟用 | ✅ 可信 |
| RLAC / CLAC(row/column 存取控制) | 強(引擎注入 Filter) | 中高 | 需定義規則 + **傳身份** | 🟡 能力可信,落地取決於身份鏈 |
| SQL firewall(strict mode) | 強(威脅模型成熟) | 中高 | ❌ **預設關** | 🟡 開了才可信 |
| dry-plan / dry-run 驗證 | 中 | 中 | 需呼叫端主動用 | 🟡 輔助性 |
| 身份傳遞(誰在問) | 弱(預設 CLI 沒接) | 低 | 需外部 gateway | 🔴 缺口 |
| 單一 DB credential 模型 | —(架構如此) | — | 共用 service account | 🔴 繞過即失防護 |
| 大量結果保護(limit/stream) | 弱(無預設上限、無 stream) | 低 | 無 | 🔴 缺口 |
| 結果 rows 進 LLM(DLP) | 弱(legacy 會塞、main 交給 agent) | 低 | 無管控 | 🔴 缺口 |
| 審計 / 審批 / rate limit | ❌ 無 | — | 不存在 | 🔴 缺口 |

圖例:✅ 可直接信任 / 🟡 有條件可信(需正確設定或補強) / 🔴 明確缺口,需外部補齊

---

## 5.3 四個原始問題的最終回答

**Q1. text2SQL 怎麼做、MDL 如何介入?**
LLM 拿到的是 MDL 編譯的「帶語意 DDL」(含 description + 計算式),不是原始 schema。
JOIN/計算欄位/方言由 Rust 引擎 deterministic 展開,LLM 只產「對語意層的邏輯 SQL」。
這確實從架構上壓低 JOIN/欄位/聚合錯誤,不是靠 LLM 更聰明。**可信。**(第 1 章)

**Q2. 大量結果怎麼處理?**
**幾乎沒有保護。** 無預設 LIMIT、`fetchall()` 全量進記憶體、無 streaming/分頁;
摘要走「撈全量 → 從尾端砍 50 列」而非 DB 端彙總。**企業硬缺口,需外掛。**(第 2 章)

**Q3. 使用者會操作到別人的資料嗎?**
RLAC/CLAC 是引擎層真強制(不是靠 LLM),能力值得肯定;**但預設 CLI 沒接身份、
底層單一共用 credential**,隔離正確性 100% 壓在「身份被每個查詢正確帶入 + 沒人繞過
WrenAI 直連 DB」。**這是最需要外部補強的風險。**(第 3 章)

**Q4. 安全治理實際落地如何?**
治理 = 一組原語(firewall + RLAC/CLAC + dry-plan + row limit)。SQL firewall 威脅
模型成熟(擋路徑穿越/SSRF/橫向移動/DoS)但**預設關**;審計/審批/rate limit 缺席;
結果 rows 可能進 LLM prompt(DLP 空白)。**是「可被治理的引擎」,非「治理平台」。**(第 4 章)

---

## 5.4 企業採用前必補清單(依風險排序)

| 優先 | 缺口 | 補強做法 | 補在哪層 |
|---|---|---|---|
| P0 | 身份未接 + 共用 credential | 受信任 gateway:SSO 驗證 → **後端**注入 session property → `engine.query(properties=...)`;end user 禁止直連 DB | gateway + DB |
| P0 | firewall 預設關 | 強制 `strict_mode=true` + 維護 `denied_functions` | config |
| P0 | 結果 rows 外洩 LLM | gateway 層 DLP:禁/遮罩原始 rows 進 prompt,摘要走彙總 SQL;用私有/有 DPA 的 LLM | gateway |
| P1 | 無 row limit / timeout | 強制預設 LIMIT(或 `pushdown_limit`)+ 統一 statement timeout | gateway / 連線層 |
| P1 | 無審計 | 記錄 (end user, session props, 展開 SQL, 回傳列數) | gateway |
| P2 | 無 streaming | server-side cursor + 分頁 API | 連線層 / gateway |
| P2 | 無縱深防禦 | 底層 DB 也加 RLS/row access policy(WrenAI RLAC + DB RLS 雙層) | DB |
| P2 | 無 rate limit / 審批 | gateway 層 rate limit;高風險查詢人工審批 workflow | gateway |

---

## 5.5 建議部署拓撲

```
使用者 ──SSO──▶ ┌─────────────────────────────────────────┐
                │  受信任 Gateway / BFF(你要自建的一層)     │
                │  • SSO/JWT 驗證使用者身份                   │
                │  • 由後端注入 session property(不信任前端) │
                │  • DLP:禁原始 rows 進 prompt、摘要走彙總    │
                │  • 強制 row limit / timeout / rate limit    │
                │  • 審計 log:誰、何時、什麼身份、什麼 SQL    │
                └───────────────────┬─────────────────────────┘
                                    │ engine.query(sql, properties=…)  strict_mode=true
                                    ▼
                        WrenAI(MDL 展開 + RLAC/CLAC + firewall)
                                    │  單一 service account
                                    ▼
                        資料庫(額外加 DB 層 RLS 作縱深) ← end user 禁止直連
```

WrenAI 負責它擅長的:語意正確 + 存取控制強制 + SQL firewall。
你自建的 gateway 負責 WrenAI 缺的:身份來源、DLP、資源護欄、審計、審批。

---

## 5.6 結論

- **值得用的地方**:如果你要的是「讓 agent 對業務資料產生語意正確、可版控、
  可套存取控制的 SQL」,WrenAI 的 MDL + RLAC/CLAC + firewall 是紮實的地基,
  比多數「純 LLM text2SQL」方案可信得多。
- **不能裸用的地方**:直接把 WrenAI(尤其預設設定)接給終端使用者查敏感資料,
  是危險的——身份沒接、firewall 沒開、結果無護欄、無審計。這些不是 bug,是
  「WrenAI 把這層責任設計成由部署者承擔」。
- **給你的判斷**:可以採用,但**必須把它放在一個自建的身份感知 gateway 後面**,
  並完成 5.4 的 P0 清單,才適合企業內部敏感資料場景。把它當「引擎」,不要當「產品」。

---

**上一章** → [04 安全治理](04-security-governance.md)　|　**回目錄** → [README](../README.md)
