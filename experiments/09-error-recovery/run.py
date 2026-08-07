from __future__ import annotations

import base64
import json
import tempfile
from pathlib import Path

from typer.testing import CliRunner

from wren.cli import app
from wren.config import WrenConfig, load_config
from wren.engine import WrenEngine
from wren.model.data_source import DataSource
from wren.model.error import DIALECT_SQL, ErrorCode, ErrorPhase, WrenError


manifest = {
    "catalog": "wren",
    "schema": "public",
    "models": [
        {
            "name": "orders",
            "tableReference": {"schema": "main", "table": "orders"},
            "columns": [{"name": "id", "type": "integer"}],
            "primaryKey": "id",
        }
    ],
}
encoded = base64.b64encode(json.dumps(manifest).encode()).decode()


def new_engine(*, config: WrenConfig | None = None) -> WrenEngine:
    return WrenEngine(
        encoded,
        DataSource.duckdb,
        {},
        fallback=False,
        config=config,
    )


strict_engine = new_engine(config=WrenConfig(strict_mode=True))
try:
    strict_engine.dry_plan("SELECT * FROM secret_table")
except WrenError as error:
    policy_error = error
else:
    raise AssertionError("Strict mode unexpectedly allowed an unknown table")

planning_engine = new_engine()
try:
    planning_engine.dry_plan("SELECT * FROM")
except WrenError as error:
    planning_error = error
else:
    raise AssertionError("Malformed SQL unexpectedly planned")


class ExplodingConnector:
    def query(self, sql: str, limit: int | None = None):
        raise RuntimeError("database exploded")

    def close(self) -> None:
        pass


execution_engine = new_engine()
execution_engine._connector = ExplodingConnector()
try:
    execution_engine.query("SELECT id FROM orders")
except WrenError as error:
    wrapped_execution_error = error
else:
    raise AssertionError("Exploding connector unexpectedly returned rows")


preserved = WrenError(
    ErrorCode.DATABASE_TIMEOUT,
    "database timeout",
    phase=ErrorPhase.SQL_EXECUTION,
    metadata={"retryable": True},
)


class StructuredConnector:
    def query(self, sql: str, limit: int | None = None):
        raise preserved

    def close(self) -> None:
        pass


structured_engine = new_engine()
structured_engine._connector = StructuredConnector()
try:
    structured_engine.query("SELECT id FROM orders")
except WrenError as error:
    preserved_execution_error = error
else:
    raise AssertionError("Structured connector unexpectedly returned rows")

with tempfile.TemporaryDirectory() as directory:
    home = Path(directory)
    (home / "config.json").write_text(
        '{"strict_mode": "yes"}',
        encoding="utf-8",
    )
    try:
        load_config(home)
    except WrenError as error:
        config_error = error
    else:
        raise AssertionError("Invalid configuration unexpectedly loaded")

cli_result = CliRunner().invoke(
    app,
    ["memory", "recall", "--definitely-invalid"],
)

print("policy:", policy_error)
print("planning:", planning_error)
print("execution-wrapped:", wrapped_execution_error)
print("execution-cause:", repr(wrapped_execution_error.__cause__))
print("execution-preserved:", preserved_execution_error)
print("configuration:", config_error)
print("cli-exit:", cli_result.exit_code)
print("cli-message:", cli_result.output.strip().splitlines()[-1])

assert policy_error.error_code == ErrorCode.MODEL_NOT_FOUND
assert policy_error.phase == ErrorPhase.SQL_POLICY_CHECK
assert planning_error.error_code == ErrorCode.INVALID_SQL
assert planning_error.phase == ErrorPhase.SQL_PLANNING
assert planning_error.metadata == {DIALECT_SQL: "SELECT * FROM"}
assert wrapped_execution_error.error_code == ErrorCode.GENERIC_USER_ERROR
assert wrapped_execution_error.phase == ErrorPhase.SQL_EXECUTION
assert DIALECT_SQL in wrapped_execution_error.metadata
assert isinstance(wrapped_execution_error.__cause__, RuntimeError)
assert preserved_execution_error is preserved
assert preserved_execution_error.metadata == {"retryable": True}
assert config_error.error_code == ErrorCode.GENERIC_USER_ERROR
assert config_error.phase is None
assert cli_result.exit_code == 2
assert "No such option" in cli_result.output
