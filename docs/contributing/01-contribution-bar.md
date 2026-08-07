# 01：WrenAI Contribution Bar

驗證基準：`Canner/WrenAI@9a0f032`

current rules 來自 root `AGENTS.md`、`CONTRIBUTING.md`、PR template、
`.claude/CLAUDE.md`、module-level instructions 與 CI workflows。PR #2602 將過去
review 中反覆出現的要求整理成 Contribution Bar。

## 1. Prove the problem

`fix` 需要 observed failure，不是「這段看起來危險」。

足夠的證據通常包含：

- current main 的 command / API / test；
- 實際 error、wrong result 或 invariant violation；
- unmodified main 的 negative control；
- 修正後同一 probe 變綠。

PR #2565 不是只搜尋 template 字串。作者在 current environment 執行
`wren ask --guided`，取得真實輸出，再執行其中的 recall command，觀察 usage
error。這使 `--nl` mismatch 成為 reproducible behavior。

若只是 performance/refactor，應量測 build count、memory 或 latency，不能假裝成
user-visible bug。PR #2612 明確以 refactor 送出；PR #2628 則量測 cache entry
memory 與 construction cost。

## 2. Reachability

看到 `dict.get()` 或 `isinstance` 不代表缺 guard。先畫：

```text
external/raw input
-> caller normalization
-> serde / Pydantic / parser
-> changed function
```

PR #2602 review 中，原本拿 `validate_manifest` 當 raw edge example；追 caller 後
發現它只收到已整理資料，最後改用真正接 user JSON 的
`convert_mdl_to_project`。

PR #2604 追了 legacy view shape 的四個 consumers，證明 malformed state 確實能
經 migration 到達；同時明確不修改另一個已由前置 validation 保證的 path。

## 3. Honest classification

| Type | 判準 |
|---|---|
| `fix` | current behavior 有可觀察錯誤，change 修正它 |
| `refactor` | 對外 behavior 不變，改善 structure/performance/maintainability |
| `test` | 補上未被有效執行或未保護的 contract |
| `docs` | 修正或澄清 user/maintainer-facing contract |
| `chore` | tooling、dependency、mechanical maintenance |

classification 會影響 evidence：refactor 要證明 behavior preserved；fix 要證明
old behavior wrong。

## 4. Tests must exercise behavior

弱測試：

```python
assert "--query" in template_source
```

強測試：

```text
render actual guided output
-> extract emitted command
-> invoke real CLI
-> assert no usage error
```

PR #2565 採後者。PR #2603 更直接展示 test double 的危險：Snowflake tests 因
mock path 錯誤，11 個 test body 根本沒進入；修正後才暴露 stale assertion。

## 5. CI awareness

先確認：

- 哪個 workflow 會被 path filter 觸發；
- test marker / directory 是否被 job 收進去；
- optional extra 是否安裝；
- connector integration 是否有 service；
- failure 是否也存在於 unmodified main。

PR #2565 遇到 Redshift CI failure，作者以 main negative control 證明它不是這個
template change 引入。PR #2603 也記錄 Snowflake file 當時不在 default CI path，
所以「local tests fixed」不等於「future regression protected」。

本 lab 的 served-content candidate 顯示另一種 CI 誤判：test comment 還假設
memory group 需要 optional extra，但 current CLI 已永遠註冊它。先 inspect 真實
command tree，才知道 dependency excuse 已失效。

## 6. Duplicate check

coding 前搜尋：

- open/closed issues；
- open/merged PRs；
- recent commits/changelog；
- repository tests 與 comments 中的 issue references。

相同 symptom 可能已有修正；相同 root cause 也可能正被一個 cohesive PR 處理。
duplicate check 要在準備 upstream action 前再跑一次，因為 backlog 會過期。

## 7. One cohesive change

不要把一個 mechanical invariant 分成多個容易漂移的 PR，也不要把相鄰但未證明的
enhancement 塞進同一 scope。

issue #2503 同時提到 recall flag 與 memory fetch enhancement。PR #2565 只處理
已重現的 guided recall bug；這是合理 scope control。

相反地，若一個 schema shape rule 在同一 module 的多個 sibling collections 都有
相同 reachable problem，應先判斷是否一次 cohesive fix 比連續 partial guards 更
容易 review。

## 8. Rebase before review

textual merge clean 不代表 semantic current。base branch 可能已：

- 改 validation boundary；
- 換 command option；
- 新增同一 regression test；
- 變更 CI matrix；
- 改同一 manifest invariant。

rebase 後要重跑 reproduction 與 negative control，不只是解 conflict。

## Module instructions are part of the contract

改 `core/wren` 前要讀其 `.claude/CLAUDE.md`；改 Rust、PyO3 或 WASM 也各有
module rules。root guidance 不足以描述每個 test command、dependency direction
與 known limitation。

## 提交前的 evidence packet

```text
Observed behavior:
Expected behavior:
Current upstream commit:
Reachable input path:
Minimal reproduction:
Negative control:
Source trace:
Existing issue / PR search:
Proposed classification:
Smallest cohesive fix:
Behavior-level regression test:
CI job that runs it:
Out-of-scope items:
```

沒有這個 packet，就先保留為 investigation note。

## Source anchors

- `AGENTS.md` section `Contribution Bar`
- `CONTRIBUTING.md`
- `.github/pull_request_template.md`
- `.github/workflows/`
- `core/wren/.claude/CLAUDE.md` validation-boundary section
- PR #2602
