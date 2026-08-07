# 04：從 Evidence 到 Issue / PR

## 1. Freeze the observation

記錄：

```text
upstream commit
environment
exact command
input fixture
stdout/stderr
exit code
expected invariant
```

不要先改 code 再回想 failure。

## 2. Build a negative control

至少一個：

- unmodified current main；
- same input through sibling path；
- valid flag vs invalid flag；
- single-thread vs concurrent；
- old decorator vs bounded decorator；
- malformed external input vs already-typed internal value。

negative control 可以區分 root cause 與 environment noise。

## 3. Trace the ownership boundary

把 path 寫到 symbol：

```text
public command
-> parser/loader
-> changed function
-> downstream consumer
```

若 trace 中已有 schema/type guarantee，停止加 defensive guard。

## 4. Search duplicates

使用 symptom、error text、symbol、subsystem 與相關 issue number搜尋 open/closed
issues、PRs、commits。記錄日期與 query，不要只寫「none」。

## 5. Choose the honest artifact

| Evidence | Artifact |
|---|---|
| verified defect + clear scope | issue or patch candidate |
| design trade-off / multiple valid fixes | discussion-first draft |
| docs contradict implementation | docs patch candidate |
| test doesn't execute behavior | test/fix candidate |
| cannot reproduce | investigation note / hypothesis |
| already fixed | postmortem / negative result |

## 6. Design the regression test first

問：

> 這個 test 在 old behavior 上會紅嗎？

如果不會，它不是 regression test。

優先順序：

1. public command/API；
2. stable subsystem interface；
3. narrow internal function only when public setup is impractical。

避免 source-string assertions、mock 到錯 call path、或 CI 不執行的 file。

## 7. Keep the patch cohesive

PR body 要寫：

- observed failure；
- source trace；
- why this boundary；
- regression test；
- CI evidence；
- out of scope。

不要順便重構鄰近 code，除非它是修正 invariant 的必要部分。

## 8. Handle CI honestly

若 unrelated job failure：

1. 在 unmodified base 重跑；
2. 記錄相同 failure；
3. 不把它隱藏或歸因給自己的 change；
4. 仍確認 target job 綠。

## 9. Review is architecture work

maintainer 要求改 short flag、error type、cache size 或 test path 時，回到 invariant
與 evidence；不要只 mechanically comply。PR #2628 顯示作者可用量測讓 reviewer
撤回初步建議。

## 10. Merge 後仍要追 release

記錄：

- final/squash merge commit；
- tag / package release；
- changelog；
- 是否有 follow-up issue；
- 原始 proposed fix 與 merged implementation 差異。

guided recall 的完整 lifecycle 見
[`contribution-lab/cases/guided-recall-flag`](../../contribution-lab/cases/guided-recall-flag/)。

## Local-only checklist

- [ ] reproduction committed in `contribution-lab/reproductions/`
- [ ] candidate schema complete
- [ ] source commit current
- [ ] old/new behavior captured
- [ ] duplicate search refreshed
- [ ] relevant upstream instructions read
- [ ] test runs in CI path
- [ ] issue/PR draft reviewed by user
- [ ] explicit permission obtained before any upstream action
