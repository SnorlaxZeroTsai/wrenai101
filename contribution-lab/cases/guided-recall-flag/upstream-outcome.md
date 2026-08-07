# Upstream Outcome

## Lifecycle

```text
local source discovery
-> issue #2503 (2026-07-14)
-> PR #2565 (2026-07-22)
-> review revisions
-> merged 2026-07-28
-> squash commit f242be4689a93d2da6f214c38c414352d07ebdaf
-> release wren-v0.13.2 (2026-07-28)
```

## What upstream merged

Behavior change：

```diff
- wren memory recall --nl "..."
+ wren memory recall -q "..."
```

Maintainer review 要求使用 `-q`，與其他 skill examples 的 style 一致。

Regression test：

1. invoke real `wren ask --guided`；
2. 從 rendered output 找 recall command；
3. 用 CLI runner 執行該 command；
4. assert command 不以 Typer usage error (`exit_code == 2`) 結束。

PR body 也記錄 Redshift CI failure 在 unmodified main 同樣出現，避免把 unrelated
failure 歸因於這個 change。

## Initial proposal vs merged result

| | Initial local idea | Upstream merged |
|---|---|---|
| Flag | `--query` | `-q` |
| Test target | template text | rendered workflow + real CLI |
| Protected invariant | 特定字串被替換 | agent 收到的 recall command 可被 current CLI 接受 |
| Adjacent enhancement | 尚未明確排除 | memory fetch enhancement out of scope |
| Release trace | 未知 | `wren-v0.13.2` |

upstream test 沒有只鎖死 spelling；只要 emitted command 仍是有效 public option，
contract 就成立。

## Current state

current pin `9a0f032` 已包含 fix 與 dedicated regression test。此 case 不再是
contribution candidate；它是 completed postmortem。
