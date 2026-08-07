from __future__ import annotations

import importlib.util
import os
import tempfile
from pathlib import Path


repo_root = Path(__file__).resolve().parents[2]
upstream = Path(os.environ.get("WRENAI_SRC", repo_root / ".wrenai-src"))
module_path = upstream / "core/wren/tests/unit/test_served_content_guard.py"

if not module_path.is_file():
    raise SystemExit(f"Upstream guard not found: {module_path}")

spec = importlib.util.spec_from_file_location("wren_served_guard_probe", module_path)
if spec is None or spec.loader is None:
    raise SystemExit(f"Cannot load guard module: {module_path}")

guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)

memory_flags = sorted(guard.COMMANDS["memory recall"])
print("memory-recall-flags:", memory_flags)
assert "--query" in memory_flags

original_skip = set(guard._SKIP_FLAG_VALIDATION_FOR_GROUPS)
guard._SKIP_FLAG_VALIDATION_FOR_GROUPS = set()
full_corpus_problems = guard._findings()
guard._SKIP_FLAG_VALIDATION_FOR_GROUPS = original_skip

cases = {
    "valid": "Run `wren skills get usage --full`.\n",
    "unknown-top-level": "Run `wren frobnicate --all`.\n",
    "unknown-subcommand": "Run `wren skills frobnicate`.\n",
    "ordinary-invalid-flag": ("Run `wren skills get usage --definitely-invalid`.\n"),
    "memory-invalid-current": (
        "Run `wren memory recall --definitely-invalid value`.\n"
    ),
    "semantic-invalid-sql": ('Run `wren --sql "SELECT definitely_not_valid FROM"`.\n'),
}

with tempfile.TemporaryDirectory() as directory:
    sample = Path(directory) / "sample.md"
    guard._iter_content_files = lambda: [sample]
    results: dict[str, list[str]] = {}
    for name, text in cases.items():
        sample.write_text(text, encoding="utf-8")
        results[name] = guard._findings()

    guard._SKIP_FLAG_VALIDATION_FOR_GROUPS = set()
    sample.write_text(cases["memory-invalid-current"], encoding="utf-8")
    results["memory-invalid-with-skip-removed"] = guard._findings()

print("current-corpus-with-memory-validation:", full_corpus_problems)
for name, findings in results.items():
    print(f"{name}:", findings)

assert full_corpus_problems == []
assert results["valid"] == []
assert results["unknown-top-level"] == []
assert results["semantic-invalid-sql"] == []
assert any("unknown subcommand" in item for item in results["unknown-subcommand"])
assert any("unknown flag" in item for item in results["ordinary-invalid-flag"])
assert results["memory-invalid-current"] == []
assert any(
    "unknown flag" in item for item in results["memory-invalid-with-skip-removed"]
)
