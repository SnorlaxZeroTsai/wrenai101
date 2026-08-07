from __future__ import annotations

from wren.memory.schema_indexer import describe_schema
from wren.memory.store import MemoryStore


manifest = {
    "catalog": "wren",
    "schema": "public",
    "models": [
        {
            "name": "orders",
            "columns": [
                {"name": "id", "type": "integer"},
                {"name": "total", "type": "decimal"},
            ],
        }
    ],
}


class SearchProbe:
    def _search_schema(self, query: str, **kwargs):
        return [{"text": f"search:{query}", "kwargs": kwargs}]


description = describe_schema(manifest)
probe = SearchProbe()

at_boundary = MemoryStore.get_context(
    probe,
    manifest,
    "orders",
    threshold=len(description),
)
one_over = MemoryStore.get_context(
    probe,
    manifest,
    "orders",
    threshold=len(description) - 1,
)

print("description-length:", len(description))
print("at-boundary:", at_boundary["strategy"])
print("one-over-boundary:", one_over["strategy"])

assert at_boundary["strategy"] == "full"
assert one_over["strategy"] == "search"
