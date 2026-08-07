# 學習地圖

## 舊 repository audit

第一輪重整前，repository 只有七篇進階分析與一篇 hypothetical contribution
appendix。audit 結果如下：

| Audit question | Finding | Action |
|---|---|---|
| 原本教得好的內容 | text-to-SQL 的 agent/engine 分工、大結果 limit、RLAC/CLAC、安全治理、企業風險與替代方案比較，都有 source trace | 保留原文深度並移到 `deep-dives/` |
| 對 101 太進階的內容 | 一開始就進入 legacy 分支、DataFusion planning、SDK cap、多租戶 identity 與 enterprise topology | 不刪除；改成 fundamentals 之後的第二層 |
| 缺少的基礎 | current repository map、MDL lifecycle、query lifecycle、knowledge placement、skills progressive disclosure、contribution culture | 新增六篇 fundamentals 與四篇 contributing guides |
| 過期 snapshot | 全部結論原先綁在 `a8a7519`（2026-07-09），並大量使用會漂移的 line numbers | current pin 改為 `9a0f032`；重要結論改引 commit/path/symbol，舊章加 snapshot banner |
| 應保留的 deep dives | legacy/current 分水嶺、text2SQL、大結果、data isolation、security、enterprise verdict、comparison | 使用 move 保留歷史，不重寫成淺層摘要 |
| 必須重驗的 claims | 30K context switch、rules 是否進 planner、session cache、served-content guard、limit handoff、CLAC wildcard behavior | 以 `experiments/01` 至 `06` 重驗；其他產品與 deployment claims列入 drift/backlog |

原 appendix 的技術發現仍有效，但「未來可以送的 contribution」已不成立，因此改為
issue #2503 到 release `wren-v0.13.2` 的 completed postmortem。

## 目標

完成這條路徑後，讀者應能從 source 追出：

```text
Agent
-> skill 與 context 選擇
-> MDL 上的 SQL
-> Python planning
-> Rust semantic analysis
-> connector execution
```

並能把理解轉成「invariant -> experiment -> observed failure -> regression test」
的貢獻候選，而不是從 TODO 猜 bug。

## 起點：先建立 current `main` 的心智模型

1. [WrenAI 是什麼](fundamentals/01-what-is-wrenai.md)
   - 分清 current agent-native `main` 與 frozen `legacy/v1`。
   - 分清 agent 推理與 deterministic engine。
2. [Repository 架構](fundamentals/02-repository-architecture.md)
   - 找到 Python、PyO3、Rust、WASM、skills、SDK 的責任邊界。
3. [MDL 與 semantic layer](fundamentals/03-mdl-semantic-layer.md)
   - 理解哪些業務語意能被編譯與強制。
4. [Query lifecycle](fundamentals/04-query-lifecycle.md)
   - 跟一條 SQL 從 CLI 到 connector。
5. [Context 與 memory](fundamentals/05-context-memory.md)
   - 分開 schema、rules、examples、index 與 profiles。
6. [Agent skills](fundamentals/06-agent-skills.md)
   - 以 progressive disclosure 理解 agent knowledge delivery。

每一章最後都有 source anchors 與可以否證結論的 drift trigger。

## 第二層：保留原有深度

| 主題 | 文件 | 閱讀前提 |
|---|---|---|
| main / legacy 歷史分水嶺 | [legacy-v1-architecture](deep-dives/legacy-v1-architecture.md) | fundamentals 01 |
| text-to-SQL 真實邊界 | [text2sql](deep-dives/text2sql.md) | fundamentals 03-05 |
| 大量結果與 limit | [large-result-handling](deep-dives/large-result-handling.md) | fundamentals 04 |
| RLAC / CLAC | [data-isolation](deep-dives/data-isolation.md) | fundamentals 03 |
| SQL policy 與治理 | [security-governance](deep-dives/security-governance.md) | fundamentals 04-05 |
| 企業採用 | [enterprise-verdict](deep-dives/enterprise-verdict.md) | 前述 deep dives |
| 替代方案比較 | [comparison](deep-dives/comparison.md) | 視為 2026-07 歷史比較，使用前重驗 |

進階文件來自舊 snapshot `a8a7519` 的研究。沒有被刪除，但 current status 以
[`UPSTREAM_STATE.md`](../UPSTREAM_STATE.md) 為準；舊行號不是永久 API。

## 第三層：用貢獻驗證理解

1. [Contribution Bar](contributing/01-contribution-bar.md)
2. [Merged PR patterns](contributing/02-merged-pr-patterns.md)
3. [Finding opportunities](contributing/03-finding-opportunities.md)
4. [Issue to PR](contributing/04-issue-to-pr.md)
5. [Contribution Lab](../contribution-lab/README.md)

第一個完整 postmortem 是
[`wren ask --guided` recall flag](../contribution-lab/cases/guided-recall-flag/)。
它展示一行修正如何在 upstream review 後變成行為層 regression test。

## 實驗順序

| 實驗 | 問題 |
|---|---|
| [`01-query-lifecycle`](../experiments/01-query-lifecycle/) | MDL SQL 實際如何展開？ |
| [`02-context-threshold`](../experiments/02-context-threshold/) | 30K 字元邊界如何切換 full/search？ |
| [`03-rules-boundary`](../experiments/03-rules-boundary/) | rules 是 agent context 還是 engine filter？ |
| [`04-served-content-guard`](../experiments/04-served-content-guard/) | executable-doc guard 能抓哪些 drift？ |
| [`05-result-limits`](../experiments/05-result-limits/) | limit 是在哪一層加上的？ |
| [`06-access-control`](../experiments/06-access-control/) | access-control invariant 應在哪裡驗證？ |
| [`07-validation-boundaries`](../experiments/07-validation-boundaries/) | raw YAML/JSON 與 typed manifest 的 reject boundary 在哪？ |
| [`08-memory-recall`](../experiments/08-memory-recall/) | Markdown source 在 grep fallback 下是否仍 durable？ |
| [`09-error-recovery`](../experiments/09-error-recovery/) | semantic、DB、config、CLI error 如何跨 boundary？ |

## 第一輪 source archaeology 優先區

1. **Agent skills / served content**：已開始並重現 memory flag coverage gap。
2. **Context / MDL validation boundary**：已跑 YAML、raw import JSON 與 Rust serde
   matrix；下一步是 OSI/API input 與 semantic-invalid typed manifests。
3. **Memory / retrieval**：已追 full/search threshold、durable source 與 grep
   fallback；下一步是 stale derived index、embedding failure 與 retrieval quality。
4. **Failure recovery**：已驗 planner、connector、config 與 Typer signal；下一步是
   MCP/SDK serialization 是否保留 code、phase 與 metadata。

## 如何判斷「學會了」

不要只背模組名稱。你應能：

- 指出某個 business rule 應放在 MDL、rules 或 query example 的哪一處，以及原因；
- 說明某個錯誤在 Python edge、Rust serde、semantic analyzer 或 connector 哪層失敗；
- 寫一個能在舊行為紅、修正後綠的測試；
- 在沒有 observed failure 時，明確保留為 hypothesis。
