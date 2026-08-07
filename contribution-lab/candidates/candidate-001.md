# Candidate 001：Correct the rules-to-planner documentation boundary

Status: `verified`, local only. Proposed classification: `docs`.

## Claim under test

Upstream `docs/core/concepts/correctness.md` says dry-plan injects policy filters
from `knowledge/rules/`.

## Evidence

At `9a0f032`:

- `load_rules` reads the marker for agent context；
- `build_json` omits the marker from the engine manifest；
- `WrenEngine.dry_plan` produces SQL without the requested `is_deleted` filter。

Run `experiments/03-rules-boundary/run.py`.

## Source trace

```text
knowledge/rules/general.md
  -> load_rules
       -> context instructions / memory index / MCP

wren context build
  -> build_manifest
  -> build_json
  -> target/mdl.json
       -> WrenEngine._plan
       -> no rules input
```

## Proposed scope

Documentation correction only:

- explain agent-applied rules；
- remove engine-injection wording and example；
- distinguish typed MDL access control from Markdown guidance。

No engine behavior change is proposed.

## Duplicate check

GitHub issue searches for `knowledge/rules dry-plan` and
`policy filters business rules` returned zero results on 2026-08-07. Repeat before
upstream action.

## Draft test position

Do not add a source-string unit test. The docs change should use current valid
commands and can be covered by existing served-content validation where applicable.
