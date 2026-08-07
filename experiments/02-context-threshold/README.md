# 02：Context Threshold

## Question

`memory fetch` 的 full schema 與 semantic search strategy 如何切換？

## Hypothesis

`MemoryStore.get_context` 比較 `describe_schema` 的 character length 與 threshold；
等於 threshold 仍是 full，大於 threshold 才 search。

## Setup

script 使用 real `describe_schema` 與 `MemoryStore.get_context`，以 probe object
取代 LanceDB search，避免下載 embedding model。它測 strategy branch，不測 retrieval
quality。

## Command

```bash
$WREN_PYTHON experiments/02-context-threshold/run.py
```

## Observed result

在 `9a0f032`：

```text
at-boundary: full
one-over-boundary: search
```

## Source explanation

`schema_indexer.py::SCHEMA_DESCRIBE_THRESHOLD = 30_000`；
`MemoryStore.get_context` 使用 `len(text) <= threshold`。

## Conclusion

current switch 是 deterministic character-count branch。這個 experiment 不證明
30K 對所有語言或 model 都是最佳值。

## What could falsify this conclusion

threshold 改用 tokens、bytes、model context window，或 search strategy 不再以
full description length 決定。
