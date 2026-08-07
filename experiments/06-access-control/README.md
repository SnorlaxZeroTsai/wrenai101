# 06：RLAC / CLAC

## Question

Typed MDL access control 是否由 semantic engine enforce？Wildcard projection 與
explicit denied-column reference 是否有不同 behavior？

## Hypothesis

- RLAC 會依 session property 注入 row filter；
- denied CLAC column 在 `SELECT *` 中被移除；
- 明確 `SELECT denied_column` 會回 Permission Denied。

## Setup

script 載入 upstream `core/wren-core-py/tests/test_modeling_core.py` 的 canonical
access-control fixture。該 customer model 包含：

- RLAC：`name = @session_user`；
- CLAC：只有 `session_level == 1` 可讀 `name`；
- RLAC run：user `alice`、level `1`（column allowed）；
- CLAC run：level `2`，不提供 optional RLAC property。

直接呼叫 PyO3 `SessionContext.transform_sql`，不連 database。可用
`WRENAI_SRC` 指向其他 upstream clone。

## Command

```bash
$WREN_PYTHON experiments/06-access-control/run.py
```

## Observed result

在 `9a0f032` / `wren-core-py 0.7.3`：

- wildcard planned SQL 只投影 `id`；
- planned SQL 含 `name = 'alice'` RLAC filter；
- explicit `SELECT name` 拋 `Permission Denied`。

## Source explanation

`wren-core/core/src/logical_plan/analyze/access_control.rs` 建 filter expression；
analyzer plan 對 wildcard 與 explicit projection 採不同 CLAC behavior。

## Conclusion

RLAC/CLAC 是 typed engine semantics，不依賴 agent 記得套 Markdown rule。不過
session properties 如何連到真實 identity，仍是 deployment integration 問題。

本次也試過「RLAC predicate 使用的 column 同時被 CLAC deny」：planner 回
`Permission Denied`。在確認 upstream 對 combined-policy precedence 的 intended
contract 前，這只記為 open question，不列為 bug。

## What could falsify this conclusion

access control 移出 core、wildcard 改為 hard error、property binding contract 改變，
或 Python facade 不再傳 properties。
