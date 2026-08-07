# 03：如何找有學習價值的貢獻機會

## 目標函數

不是找最小 diff，而是找能揭露重要 invariant 的問題：

```text
Learning Value
x User Impact
x Evidence Strength
x Maintainer Fit
/ Implementation Cost
```

## 正確迴圈

```text
選 subsystem
-> 建 architecture map
-> 找 public invariant
-> 讀 implementation 與 tests
-> 讀 recent fixes
-> 設計 falsification experiment
-> 觀察 failure 或 negative result
-> 追 reachability
-> 搜 issue / PR
-> 建 candidate
```

禁止使用：

```text
grep TODO
-> 猜 edge case
-> 加 defensive guard
```

## Track A：Agent skills / served content

要理解：

- discovery stub；
- package data delivery；
- `get_skill` / references / scripts；
- ask templates；
- Typer command registration；
- served-content guard 與 optional extras；
- 哪個 CI job 真正執行 guard。

Falsification questions：

- invalid top-level command 會被抓嗎？
- known group 下 invalid subcommand 呢？
- leaf positional argument會被誤判嗎？
- renamed long flag / short flag 呢？
- optional `memory` / `mcp` command 呢？
- multi-line shell continuation 呢？

第一輪結果：memory command paths 與 real flags 都已出現在 command tree，但 guard
仍因歷史假設跳過 flags。prepared patch 移除 skip 並通過 focused suite。見
candidate 002。

## Track B：Context / MDL validation boundary

先畫：

```text
raw YAML / JSON / API response
-> Python loader/converter
-> base64 manifest
-> Rust serde
-> typed Manifest
-> semantic analyzer
```

對每個 candidate 回答：

1. value 是 raw 還是 typed？
2. 哪個 caller 產生它？
3. 之前是否已有 validator？
4. failure 是 crash、misleading error，還是 silent data loss？
5. 最早有足夠 context 的 error boundary 在哪？

目前已確認的 negative discipline：不能因 `validate_manifest` 看似接受 dict，就假設
它是 raw edge；PR #2602 review 已證明 caller trace 會改答案。

另一個完整例子是 PR #2567：consumer guard 無法保護 build 與 migration。review
把 real defect 移到 `_load_views_v1`，issue #2597 / merged PR #2604 再用五個
public-consumer tests 證明 scope。見
[`validation-boundary-review`](../../contribution-lab/review-notes/validation-boundary-review.md)。

## Track C：Memory / retrieval

分開研究：

- durable `knowledge/sql`；
- grep recall；
- LanceDB schema/query tables；
- seed examples；
- 30K full/search switch；
- manifest hash；
- embedding dimension；
- malformed collection behavior；
- `limit`、empty result、stale index。

Falsification questions：

- threshold 前後是否回不同 result shape？
- schema 變更後 stale rows 是否被 filter？
- grep fallback 是否保留 store/recall contract？
- wrong-typed nested field 是 fail 還是 silent empty？
- rules 修改後哪些 hash/index 會更新？

## Track D：Agent failure recovery

建立 error taxonomy：

| Failure | Expected signal |
|---|---|
| Project/config | actionable CLI message / exit code |
| MDL semantic | structured planning error |
| SQL policy | blocked function/model code |
| Database | preserved connector/database detail |
| Tool misuse | Typer usage error |
| Optional feature missing | install guidance，不能假裝 empty success |

追查 structured details 在 CLI、MCP、SDK serialization 中是否丟失。只有能用 public
path 重現資訊損失時，才升級成 fix candidate。

## Candidate 建立門檻

每個 candidate 必須填：

- title / subsystem；
- learning value；
- user impact；
- observed failure；
- reproduction；
- source trace；
- root cause；
- possible fix；
- behavior-level test；
- existing issue / PR / duplicate check；
- confidence；
- scope；
- recommended action。

schema 以 [`CONTRIBUTION_BACKLOG.md`](../../CONTRIBUTION_BACKLOG.md) 為準。

## Negative results

下列都是有效產出：

- invariant 已由 Rust type 保證；
- public failure message 已足夠；
- suspected command 已被 generic guard 覆蓋；
- issue 已有 active PR；
- performance difference 無法在 noise 外重現；
- current bundled content 沒有錯，但 test harness 有已知 coverage boundary。

記錄 probe、source trace 與 falsifier，避免下一輪重複猜同一件事。

## Upstream action gate

本 repository 只準備 local artifact。開 issue/PR 前必須：

1. refresh `main`；
2. rebase / rerun；
3. repeat duplicate search；
4. confirm CI path；
5.讓使用者 review candidate；
6.取得明確發布指示。
