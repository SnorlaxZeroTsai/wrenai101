# Experiments

每個 experiment 都必須包含：

```text
Question
Hypothesis
Setup
Command
Observed result
Source explanation
Conclusion
What could falsify this conclusion
```

## Environment

在 pinned upstream 建立 Python environment：

```bash
cd .wrenai-src/core/wren
uv sync --python 3.12 --group dev
```

以下 README 用 `$WREN_PYTHON` 表示該 environment 的 Python：

```bash
export WREN_PYTHON="$PWD/.wrenai-src/core/wren/.venv/bin/python"
```

本次 recorded results 使用 upstream `9a0f032` 與 Python 3.12.13。重新跑在其他
commit 時，不要覆寫舊結論；先記錄 drift。

## Experiments

| Directory | Architecture question |
|---|---|
| `01-query-lifecycle` | MDL model/calculated field 如何出現在 planned SQL？ |
| `02-context-threshold` | full context 與 search 的邊界如何選？ |
| `03-rules-boundary` | rules 是否進 engine manifest 與 dry-plan？ |
| `04-served-content-guard` | guard 能否驗證 optional memory flags？ |
| `05-result-limits` | `WrenEngine` 是否自行加 default limit？ |
| `06-access-control` | RLAC 與 CLAC 在 semantic engine 如何表現？ |
| `07-validation-boundaries` | malformed YAML/JSON/manifest 分別在哪層被拒絕？ |
| `08-memory-recall` | 沒有 vector dependencies 時 query memory 是否仍 durable？ |
| `09-error-recovery` | 哪些 error code、phase、metadata 與 exit signal 被保留？ |
