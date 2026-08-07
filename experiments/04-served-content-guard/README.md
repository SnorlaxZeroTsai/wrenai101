# 04：Served-content Guard

## Question

Generic served-content guard 對 command、subcommand、flag、semantic example 與
cross-document drift 的實際 coverage boundary 是什麼？

## Hypothesis

它會抓 known group 的 invalid subcommand 與一般 invalid flag；unknown top-level
token與 SQL semantic validity不在 current model。memory flags 本來可 introspect，
但 stale skip 讓它漏報。

## Setup

script 載入 upstream real guard，測 valid command、unknown top-level command、
unknown subcommand、ordinary invalid flag、memory invalid flag、invalid SQL example，
並模擬移除 memory skip。它也對完整 current corpus 啟用 memory validation。

## Command

```bash
cd .wrenai-src/core/wren
$WREN_PYTHON -m pytest tests/unit/test_served_content_guard.py -q
cd ../../..
$WREN_PYTHON experiments/04-served-content-guard/run.py
```

可用 `WRENAI_SRC` 指向其他 upstream clone root。

## Observed result

在 `9a0f032`：

```text
upstream baseline: 4 passed
known-subcommand: finding
ordinary-invalid-flag: finding
memory-invalid-current: []
memory-invalid-with-skip-removed: finding
unknown-top-level: []
semantic-invalid-sql: []
current-corpus-with-memory-validation: []
```

## Source explanation

guard 設定：

```python
_SKIP_FLAG_VALIDATION_FOR_GROUPS = {"memory"}
```

但 current `cli.py` always registers `memory_app`；runtime `COMMANDS` 已含 real flags。
unknown top-level tokens 被當 prose 跳過，SQL example 只驗 CLI syntax，不做 DB/MDL
semantic execution。

## Conclusion

memory skip 是 verified stale exception，prepared small patch 已通過。unknown
top-level 與 semantic examples 是明確記錄的 scanner scope，不在此 candidate 中
假裝成 bug。cross-document drift 只在 drift 表現為 invalid CLI reference 時被抓。

## What could falsify this conclusion

scanner 改用 Markdown-aware executable-block parsing、加入 SQL/MDL execution，
或 served-content architecture 不再依賴 CLI command references。
