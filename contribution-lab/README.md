# Contribution Lab

這裡保存從 architecture learning 到 contribution candidate 的完整證據。

```text
cases/           已完成或已被 upstream 處理的 lifecycle postmortem
candidates/      尚未發布的 evidence-backed candidates
reproductions/   可重跑 probes 與 raw observed output
review-notes/    maintainer patterns、PR sample、CI notes
```

## Candidate states

```text
hypothesis -> reproduced -> verified -> user review -> upstream action
```

`verified` 只表示 current pin 上的 failure、reachability 與 source cause 已被確認，
不代表 maintainer 一定同意 fix design。

## Rules

- 沒有 observed failure 不叫 bug。
- negative result 要留下。
- issue/PR search 會過期，upstream action 前必須重跑。
- local patch 可以準備；未經明確指示不得發布。
- 每個 case 最後要寫「可泛化的 architecture lesson」。

Rejected 或 re-scoped work 也要留下 review trace。PR #2567 到 merged PR #2604 的
guard-placement lesson 在
[`review-notes/validation-boundary-review.md`](review-notes/validation-boundary-review.md)。
