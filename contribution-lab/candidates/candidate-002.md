# Candidate 002：Served-content memory flag validation

Status: `verified`, patch prepared and tested locally. Proposed classification:
`test`.

## Observed behavior

At `9a0f032`:

```text
injected: wren memory recall --definitely-invalid value
guard findings: []

injected: wren skills get usage --definitely-invalid
guard findings: [unknown flag ...]
```

Baseline upstream guard suite remains green: `4 passed`.

## Reachability

The gap is intentional in current test code:

```python
_SKIP_FLAG_VALIDATION_FOR_GROUPS = {"memory"}
```

The reason recorded beside it is no longer true. Current
`core/wren/src/wren/cli.py` says the memory group is always registered and imports
heavy dependencies lazily. Runtime inspection confirms:

```text
COMMANDS["memory recall"] =
  --datasource --limit --output --path --query
```

With the skip disabled, the full current served corpus reports zero problems.

## What this does not prove

- It does not prove current bundled content contains an invalid memory flag.
- It does not prove unknown top-level commands or semantically invalid SQL examples
  are covered; they are separate scanner boundaries.

## Prepared fix

`candidate-002.patch`:

1. removes the obsolete manual memory subcommand allow-list;
2. removes the memory flag-validation skip;
3. asserts real memory flags exist in the command tree;
4. adds a mutation test for an invalid memory flag.

The artifact is a zero-context patch, pinned to `9a0f032`:

```bash
git apply --unidiff-zero candidate-002.patch
```

Verified in a detached worktree at `9a0f032`:

```text
pytest test_served_content_guard.py: 5 passed
ruff check: passed
ruff format --check: passed
```

## Required regression

The regression fails on current main because the injected invalid flag is skipped,
and passes with the prepared patch. Existing corpus validation exercises current
valid long options using the real command definition.

Run `experiments/04-served-content-guard/run.py`.

## Duplicate check

Searches on 2026-08-07 found PR #2329, which introduced the generic guard and its
real-command-tree strategy. No issue or PR specifically removed the intentional
memory flag skip. This search must be repeated before upstream action.
