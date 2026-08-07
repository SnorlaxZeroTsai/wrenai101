# 05：Result Limit Handoff

## Question

`WrenEngine.query` 是否在 caller 沒提供 limit 時，自行加入 default row cap？

## Hypothesis

Python facade 只把 `limit` 原樣交給 connector；`None` 仍是 `None`。SDK tool 或
individual connector 可以有自己的 cap，但不是 `WrenEngine` 的 universal default。

## Setup

script 將 fake connector 注入 `WrenEngine`，避開 database。它呼叫兩次 query：
一次 `limit=None`，一次 `limit=7`，記錄 connector 收到的值。

## Command

```bash
$WREN_PYTHON experiments/05-result-limits/run.py
```

## Observed result

在 `9a0f032`：

```text
connector-limits: [None, 7]
```

## Source explanation

`WrenEngine.query` 呼叫 `connector.query(dialect_sql, limit)`，沒有在 facade 層替
`None` 設 default。

## Conclusion

不能把 agent SDK tool cap 當成所有 CLI/SDK query 的 engine guarantee。要判斷資源
護欄，必須逐 caller 與 connector trace。

## What could falsify this conclusion

`WrenEngine.query` 新增 default cap、config 在進 connector 前改寫 limit，或 public
CLI 永遠強制傳非-None。
