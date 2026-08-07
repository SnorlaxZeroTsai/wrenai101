# Lessons

## 1. 一行修正不等於完整貢獻

diff 的核心只有一行，但 contribution 的價值來自：

- current failure reproduction；
- public path reachability；
- behavior-level regression；
- CI negative control；
- scope boundary；
- release follow-through。

## 2. Test the invariant, not the typo

真正 invariant：

> served agent instruction 必須能被同版本 CLI 執行。

`assert "--nl" not in template` 只防一個 typo；real CLI invocation 也能防未來 rename、
registration 或 option drift。

## 3. Maintainer feedback often encodes ecosystem consistency

`--query` 與 `-q` 都可執行，但 maintainer 選 `-q` 是為了與 current skills examples
一致。review 不只判斷 correctness，也管理 public vocabulary。

## 4. Keep adjacent requests out of a proven fix

issue 內的 memory fetch enhancement 沒有與 flag mismatch 綁在同一 PR。這讓
regression、risk 與 release note 都更清楚。

## 5. Generalize without overclaiming

這個 case 推動了 generic served-content guard 的研究，但不能反推「所有 served
content 都有 bug」。後續只證明一個 stale memory skip；current bundled content
在啟用完整 memory flag validation 後仍是 clean。

## Reusable checklist

```text
render actual agent-facing output
-> extract executable instruction
-> invoke the real tool
-> assert public behavior
-> run a valid control
-> identify optional-feature CI gaps
```
