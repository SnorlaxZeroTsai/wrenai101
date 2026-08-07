from __future__ import annotations

import builtins
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from wren.cli import app


runner = CliRunner()
real_import = builtins.__import__


def import_without_memory_extra(name, globals=None, locals=None, fromlist=(), level=0):
    if name == "wren.memory.store":
        error = ModuleNotFoundError("No module named 'lancedb'")
        error.name = "lancedb"
        raise error
    return real_import(name, globals, locals, fromlist, level)


def invoke(args: list[str], env: dict[str, str]):
    result = runner.invoke(app, args, env=env)
    if result.exit_code != 0:
        raise AssertionError(
            f"Command failed ({result.exit_code}): {' '.join(args)}\n"
            f"{result.output}\n{result.exception!r}"
        )
    return result


with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    project = root / "project"
    project.mkdir()
    (project / "wren_project.yml").write_text(
        "schema_version: 5\nname: memory-recall\ndata_source: duckdb\n",
        encoding="utf-8",
    )
    env = {
        "WREN_PROJECT_HOME": str(project),
        "WREN_MEMORY_BACKEND": "grep",
        "WREN_HOME": str(root / "wren-home"),
    }

    with patch("builtins.__import__", side_effect=import_without_memory_extra):
        first_store = invoke(
            [
                "memory",
                "store",
                "--nl",
                "What is total revenue?",
                "--sql",
                "SELECT SUM(total) AS revenue FROM orders",
                "--datasource",
                "duckdb",
                "--tags",
                "revenue,finance",
            ],
            env,
        )
        updated_store = invoke(
            [
                "memory",
                "store",
                "--nl",
                "What is total revenue?",
                "--sql",
                "SELECT SUM(net_total) AS revenue FROM orders",
                "--datasource",
                "duckdb",
            ],
            env,
        )
        invoke(
            [
                "memory",
                "store",
                "--nl",
                "List orders by customer",
                "--sql",
                "SELECT customer_id, COUNT(*) FROM orders GROUP BY customer_id",
                "--datasource",
                "duckdb",
            ],
            env,
        )

    sources = sorted((project / "knowledge" / "sql").glob("*.md"))
    recall = invoke(
        [
            "memory",
            "recall",
            "--query",
            "revenue",
            "--limit",
            "1",
            "--output",
            "json",
        ],
        env,
    )
    rows = json.loads(recall.output)
    status = invoke(["memory", "status"], env)
    check = invoke(["memory", "check"], env)
    reset = invoke(["memory", "reset"], env)
    recall_after_reset = invoke(
        [
            "memory",
            "recall",
            "--query",
            "revenue",
            "--limit",
            "1",
            "--output",
            "json",
        ],
        env,
    )
    rows_after_reset = json.loads(recall_after_reset.output)

print(first_store.output.strip())
print(updated_store.output.strip())
print("source-files:", [path.name for path in sources])
print("recall:", rows)
print(status.output.strip())
print(check.output.strip())
print(reset.output.strip())
print("recall-after-reset:", rows_after_reset)

assert len(sources) == 2
assert len(rows) == 1
assert rows[0]["nl_query"] == "What is total revenue?"
assert rows[0]["sql_query"] == "SELECT SUM(net_total) AS revenue FROM orders"
assert rows[0]["datasource"] == "duckdb"
assert rows[0]["path"].startswith("knowledge/sql/")
assert rows[0]["score"] > 0
assert "Backend: grep" in status.output
assert "2 pair(s)" in status.output
assert "always in sync" in check.output
assert "has no derived index" in reset.output
assert rows_after_reset == rows
