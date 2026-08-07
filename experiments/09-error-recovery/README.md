# 09：Structured Error Recovery

## Question

semantic/policy、planning、database、configuration 與 CLI misuse failures 經過
current public boundaries 後，哪些結構被保留，哪些會被正規化？

## Hypothesis

planner 與 connector 已產生的 `WrenError` 會保留；arbitrary connector exception
會被包成 execution-phase generic error，但附 planned SQL 與 Python cause；config
loader 使用 error code 但沒有 phase；Typer misuse 使用 exit code 2 與 usage text。

## Setup

script 使用一個 minimal manifest，依序觸發：

1. strict-mode unknown table；
2. malformed SQL；
3. connector `RuntimeError`；
4. connector 已產生的 `DATABASE_TIMEOUT` `WrenError`；
5. wrong-typed `config.json`；
6. invalid CLI flag。

不連接 real database。

## Command

```bash
$WREN_PYTHON experiments/09-error-recovery/run.py
```

## Observed result

在 `9a0f032`：

```text
policy: MODEL_NOT_FOUND / SQL_POLICY_CHECK
planning: INVALID_SQL / SQL_PLANNING
execution-wrapped: GENERIC_USER_ERROR / SQL_EXECUTION
execution-cause: RuntimeError('database exploded')
execution-preserved: DATABASE_TIMEOUT / SQL_EXECUTION
configuration: GENERIC_USER_ERROR / no phase
cli-exit: 2 / No such option
```

wrapped execution error 的 metadata 含 planned target-dialect SQL；原本已 structured
的 connector error object 與其 metadata 原樣保留。

## Source explanation

`WrenEngine.query` 明確 `except WrenError: raise`，其他 exception 才轉成
`GENERIC_USER_ERROR` 並附 `ErrorPhase.SQL_EXECUTION` 與 `dialectSql`。policy 與
planning 在更早邊界建立自己的 code/phase。`load_config` 是 startup boundary，
產生 `WrenError` 但沒有 phase。Typer parser 在 command callback 前處理 misuse，
因此 contract 是 process exit/status text，不是 engine exception。

## Conclusion

failure recovery 不是單一 exception channel。in-process agent/SDK 應優先使用
`error_code`、`phase` 與 metadata；subprocess caller 必須另外解析 exit code 和
stderr。這個 probe 沒有觀察到 structured connector error 被 `WrenEngine` 降級，
因此不建立 bug candidate。是否在 MCP/SDK serialization 後丟失欄位仍是後續研究。

## What could falsify this conclusion

engine 改為重新包裝所有 connector errors、config errors 加入 phase、CLI 將
`WrenError` 序列化成 machine-readable output，或 MCP/SDK 成為唯一 supported
execution boundary。
