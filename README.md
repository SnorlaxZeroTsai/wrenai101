# WrenAI 101: 原始碼學習與開源貢獻實驗室

這個 repository 用目前的 `Canner/WrenAI` 原始碼學習 WrenAI，並把開源貢獻當成
驗證理解的方法。它不是產品介紹，也不是一次性的企業評估報告。

目前驗證基準：

- upstream: `Canner/WrenAI`
- branch: `main`
- commit: `9a0f0324307442cb523b43838f391add328b78f9`
- reviewed: 2026-08-07
- Python package: `wrenai 0.13.2`

重要結論一律要回答三件事：

1. 在哪個 commit、檔案與 symbol 看到？
2. 是 source trace、實驗結果，還是假說？
3. 哪個 upstream 變更會讓它失效？

## 這裡的 101 是什麼

內容分兩層：

- **Fundamentals**：先理解 repository、MDL、query lifecycle、context、memory 與 skills。
- **Deep dives**：保留原有的 text-to-SQL、結果限制、RLAC/CLAC、安全與企業採用研究。

建議從 [學習地圖](docs/00-learning-map.md) 開始。

```text
Agent
  -> discovery skill / served workflow
  -> context instructions + memory fetch/recall
  -> SQL against MDL
  -> Python WrenEngine
  -> PyO3 SessionContext
  -> Rust wren-core semantic planning
  -> connector
  -> database
```

LLM/agent 負責理解問題、選 context、產生與修正 SQL。WrenAI 的 deterministic
邊界負責 MDL 結構、語意展開、policy 檢查、方言轉換與執行。兩者不能混稱為
「text-to-SQL 引擎」。

## Repository 導覽

| 路徑 | 用途 |
|---|---|
| [`docs/fundamentals/`](docs/fundamentals/) | 從零建立 current `main` 架構模型 |
| [`docs/deep-dives/`](docs/deep-dives/) | 原有進階研究，保留其技術深度 |
| [`docs/contributing/`](docs/contributing/) | WrenAI Contribution Bar 與 maintainer review patterns |
| [`experiments/`](experiments/) | 可重跑的架構實驗，不只靠閱讀推論 |
| [`contribution-lab/`](contribution-lab/) | case study、候選貢獻、重現與 review notes |
| [`UPSTREAM_STATE.md`](UPSTREAM_STATE.md) | upstream pin、變更與待複查範圍 |
| [`LEARNING_BACKLOG.md`](LEARNING_BACKLOG.md) | 下一輪 source archaeology |
| [`CONTRIBUTION_BACKLOG.md`](CONTRIBUTION_BACKLOG.md) | 有證據且做過 duplicate check 的候選項目 |

## 已驗證的第一輪發現

1. `knowledge/rules/*.md` 是 agent-facing context，也可進 memory index；一般
   `wren context build` 不會把它編進 engine manifest。current correctness guide
   所稱 dry-plan 會注入這些 policy filters，與實際 source path 不一致。
2. served-content guard 會驗證實際 Typer/Click command tree。current CLI 已永遠
   註冊 lightweight memory group，真實 flags 也可 introspect，但 guard 仍保留舊的
   memory skip。移除 skip 後 current content 全部通過，且 invalid memory flag 會被
   抓到；candidate patch 已在 isolated worktree 驗證。
3. 舊附錄中的 guided-recall bug 已由 issue #2503、PR #2565、regression test、
   merge commit `f242be4` 與 `wren-v0.13.2` 完成 upstream lifecycle。

證據與可重跑指令分別在
[`03-rules-boundary`](experiments/03-rules-boundary/)、
[`04-served-content-guard`](experiments/04-served-content-guard/) 與
[`guided-recall-flag`](contribution-lab/cases/guided-recall-flag/)。

## 使用方式

本 repository 不追蹤 upstream clone。預設把它放在 `.wrenai-src/`：

```bash
git clone https://github.com/Canner/WrenAI.git .wrenai-src
git -C .wrenai-src checkout 9a0f0324307442cb523b43838f391add328b78f9
```

跑實驗前先看各目錄 README。實驗記錄的 `Observed result` 是在上述 commit 的
輸出，不保證未來版本相同。

## 貢獻界線

這裡可以準備 reproduction、regression test、patch、issue draft 與 PR draft，
但不會自動開 issue、push branch、送 PR 或在 upstream 留言。任何 upstream
發布動作都需要使用者明確指示。
