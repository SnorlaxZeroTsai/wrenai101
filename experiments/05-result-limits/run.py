from __future__ import annotations

import pyarrow as pa

from wren import WrenEngine
from wren.model.data_source import DataSource


class ConnectorProbe:
    def __init__(self):
        self.limits: list[int | None] = []

    def query(self, sql: str, limit: int | None):
        self.limits.append(limit)
        return pa.table({"planned_sql": [sql]})

    def close(self):
        pass


engine = WrenEngine("", DataSource.duckdb, {})
probe = ConnectorProbe()
engine._connector = probe
engine.dry_plan = lambda sql, properties=None: f"PLANNED({sql})"

engine.query("SELECT 1")
engine.query("SELECT 1", limit=7)

print("connector-limits:", probe.limits)
assert probe.limits == [None, 7]
