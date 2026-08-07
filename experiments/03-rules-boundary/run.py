from __future__ import annotations

import base64
import json
import tempfile
from pathlib import Path

from wren import WrenEngine
from wren.context import build_json, load_rules
from wren.model.data_source import DataSource


with tempfile.TemporaryDirectory() as directory:
    project = Path(directory)
    (project / "wren_project.yml").write_text(
        "schema_version: 5\n"
        "name: rules_probe\n"
        "data_source: duckdb\n"
        "catalog: wren\n"
        "schema: public\n",
        encoding="utf-8",
    )

    model = project / "models" / "orders"
    model.mkdir(parents=True)
    (model / "metadata.yml").write_text(
        "name: orders\n"
        "table_reference:\n"
        "  schema: main\n"
        "  table: orders\n"
        "columns:\n"
        "  - name: id\n"
        "    type: integer\n"
        "  - name: is_deleted\n"
        "    type: boolean\n",
        encoding="utf-8",
    )

    rules = project / "knowledge" / "rules"
    rules.mkdir(parents=True)
    marker = "ALWAYS_FILTER_IS_DELETED_FALSE"
    (rules / "general.md").write_text(f"{marker}\n", encoding="utf-8")

    manifest = build_json(project)
    loaded_rules, _ = load_rules(project)
    encoded = base64.b64encode(json.dumps(manifest).encode()).decode()
    engine = WrenEngine(
        encoded,
        DataSource.duckdb,
        {"url": directory, "format": "duckdb"},
        fallback=False,
    )
    planned = engine.dry_plan("SELECT id FROM orders")

    print("rules-loaded-for-agent:", marker in (loaded_rules or ""))
    print("rules-in-engine-manifest:", marker in json.dumps(manifest))
    print("planned-sql:", planned)
    print("filter-injected:", "is_deleted" in planned.lower())

    assert marker in (loaded_rules or "")
    assert marker not in json.dumps(manifest)
    assert "is_deleted" not in planned.lower()
