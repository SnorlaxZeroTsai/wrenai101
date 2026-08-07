from __future__ import annotations

import base64
import json

from wren import WrenEngine
from wren.model.data_source import DataSource


manifest = {
    "catalog": "wren",
    "schema": "public",
    "models": [
        {
            "name": "orders",
            "tableReference": {"schema": "main", "table": "orders"},
            "columns": [
                {"name": "id", "type": "integer"},
                {"name": "customer_id", "type": "integer"},
                {
                    "name": "order_key",
                    "type": "varchar",
                    "expression": (
                        "concat(cast(id as varchar), '_', cast(customer_id as varchar))"
                    ),
                },
            ],
            "primaryKey": "id",
        }
    ],
}

encoded = base64.b64encode(json.dumps(manifest).encode()).decode()
engine = WrenEngine(
    encoded,
    DataSource.duckdb,
    {"url": "/tmp/wrenai101-query-lifecycle", "format": "duckdb"},
    fallback=False,
)

planned = engine.dry_plan("SELECT order_key FROM orders")

print(planned)
print("connector-opened:", engine._connector is not None)

assert '"main".orders' in planned
assert "concat" in planned.lower() or "||" in planned
assert engine._connector is None
