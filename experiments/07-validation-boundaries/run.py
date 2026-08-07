from __future__ import annotations

import base64
import json
import tempfile
from pathlib import Path

from wren.context import build_json, convert_mdl_to_project, validate_project
from wren_core import ManifestExtractor


with tempfile.TemporaryDirectory() as directory:
    project = Path(directory)
    (project / "wren_project.yml").write_text(
        "schema_version: 1\n"
        "name: validation-boundary\n"
        "data_source: duckdb\n"
        "catalog: wren\n"
        "schema: public\n",
        encoding="utf-8",
    )
    models = project / "models"
    models.mkdir()
    (models / "orders.yml").write_text(
        "name: orders\n"
        "table_reference:\n"
        "  table: orders\n"
        "columns:\n"
        "  - name: id\n"
        "    type: INTEGER\n"
        "primary_key: id\n",
        encoding="utf-8",
    )
    (project / "views.yml").write_text(
        "views:\n  - null\n  - junk\n  - name: summary\n    statement: SELECT 1\n",
        encoding="utf-8",
    )

    validation_errors = validate_project(project)
    view_entry_errors = [
        error for error in validation_errors if "must be a mapping" in error.message
    ]
    built = build_json(project)

print("yaml-validation-errors:")
for error in view_entry_errors:
    print(" ", error)
print("built-views:", [view["name"] for view in built["views"]])

assert {error.path for error in view_entry_errors} == {
    "views.yml > views[0]",
    "views.yml > views[1]",
}
assert [view["name"] for view in built["views"]] == ["summary"]

try:
    convert_mdl_to_project({"models": [42]})
except Exception as error:
    raw_converter_error = error
else:
    raise AssertionError("Raw MDL converter unexpectedly accepted an integer model")

malformed_manifest = {
    "catalog": "wren",
    "schema": "public",
    "models": [42],
}
encoded = base64.b64encode(json.dumps(malformed_manifest).encode()).decode()
try:
    ManifestExtractor(encoded)
except Exception as error:
    rust_serde_error = error
else:
    raise AssertionError(
        "Rust manifest extractor unexpectedly accepted an integer model"
    )

print(
    "raw-converter-error:",
    type(raw_converter_error).__name__,
    str(raw_converter_error),
)
print("rust-serde-error:", type(rust_serde_error).__name__, str(rust_serde_error))

assert isinstance(raw_converter_error, TypeError)
assert "not iterable" in str(raw_converter_error)
assert "Serde JSON error" in str(rust_serde_error)
assert "invalid type" in str(rust_serde_error)
