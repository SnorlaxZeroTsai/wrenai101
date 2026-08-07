# Discovery：guided recall flag mismatch

## Local observation

舊 snapshot 的 guided ask template 會產生：

```bash
wren memory recall --nl "<question>"
```

但 `memory recall` 的 Typer option 是：

```text
--query / -q
```

執行 emitted command 會得到 CLI usage error，而不是 recall result。

## Source trace

```text
wren ask --guided
-> guided ask template render
-> emitted recall instruction
-> Typer memory_app
-> recall(query: Option("--query", "-q"))
```

這是 public instruction 與 public CLI contract 的 mismatch，不是 LLM output
quality 問題。

## Initial local proposal

最初想法是：

1. template 的 `--nl` 改為 `--query`；
2. 加一個 assertion 檢查 template 不再含 `--nl`。

第一項修 behavior；第二項只保護文字，不證明 instruction 可執行。upstream 最終
採更強的 test。

## Upstream issue

Issue #2503 在 2026-07-14 以 `wrenai 0.13.0` 與 Windows environment 報告：

- exact `wren ask "test" --guided` reproduction；
- emitted `--nl` error；
- valid `--query/-q` contract；
- regression test request。

issue 同時提到 memory fetch enhancement。後續 PR 沒把它一起做，保持 bug fix
scope。

## Evidence classification

```text
observed: yes
reachable: yes, through rendered guided workflow
current at discovery: yes
duplicate at discovery: upstream issue #2503 became canonical report
classification: fix
```
