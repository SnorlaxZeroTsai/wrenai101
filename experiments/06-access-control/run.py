from __future__ import annotations

import importlib.util
import os
from pathlib import Path

from wren_core import SessionContext


repo_root = Path(__file__).resolve().parents[2]
upstream = Path(os.environ.get("WRENAI_SRC", repo_root / ".wrenai-src"))
fixture_path = upstream / "core/wren-core-py/tests/test_modeling_core.py"

if not fixture_path.is_file():
    raise SystemExit(f"Upstream access-control fixture not found: {fixture_path}")

spec = importlib.util.spec_from_file_location("wren_core_access_fixture", fixture_path)
if spec is None or spec.loader is None:
    raise SystemExit(f"Cannot load access-control fixture: {fixture_path}")

fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)

rlac_properties = frozenset(
    {
        "session_user": "'alice'",
        "session_level": "1",
    }.items()
)
rlac_session = SessionContext(fixture.manifest_str, None, rlac_properties)

rlac_sql = rlac_session.transform_sql("SELECT * FROM my_catalog.my_schema.customer")
print("rlac:", rlac_sql)
assert "c_name = 'alice'" in rlac_sql

clac_properties = frozenset({"session_level": "2"}.items())
clac_session = SessionContext(fixture.manifest_str, None, clac_properties)

wildcard = clac_session.transform_sql("SELECT * FROM my_catalog.my_schema.customer")
print("clac-wildcard:", wildcard)

projection = wildcard.split(" FROM ", 1)[0]
assert "customer.c_custkey" in projection
assert "customer.c_name" not in projection

try:
    clac_session.transform_sql("SELECT c_name FROM my_catalog.my_schema.customer")
except Exception as error:
    print("explicit-column-error:", error)
    assert "Permission Denied" in str(error)
else:
    raise AssertionError("Explicit denied column unexpectedly planned")
