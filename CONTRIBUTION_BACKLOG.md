# Contribution Backlog

Ranking is conceptual:

```text
Learning Value
x User Impact
x Evidence Strength
x Fit With Maintainer Direction
/ Implementation Cost
```

No item here has been published upstream.

## Candidate 001: Correct the rules-to-planner documentation boundary

```yaml
title: "Document that knowledge/rules guides agents but is not injected by dry-plan"

subsystem: "documentation / context / planning boundary"

classification: docs

learning_value:
  score: 5
  explanation: "Requires tracing project build, rules loading, memory indexing, engine manifest input, and SQL planning."

user_impact: "The correctness guide currently implies default filters in knowledge/rules are engine-enforced. A user could treat prompt guidance as a security or correctness guarantee."

observed_failure: "At commit 9a0f032, docs/core/concepts/correctness.md says dry-plan injects policy filters from knowledge/rules. A temporary v5 project loaded the marker rule for agent context, but build_json omitted it and dry_plan emitted SQL without the filter."

reproduction: "experiments/03-rules-boundary/run.py; observed rules-loaded-for-agent=True, rules-in-engine-manifest=False, filter-injected=False"

source_trace: "core/wren/src/wren/context.py::load_rules and build_manifest/build_json; core/wren/src/wren/memory/cli.py::index; core/wren/src/wren/engine.py::WrenEngine._plan"

suspected_root_cause: "The guide conflates an agent workflow obligation with an engine planning invariant."

possible_fix: "Revise correctness.md and the example trace to say the agent must load/apply rules; reserve engine-enforced wording for MDL semantics, policy.py, and RLAC/CLAC."

test_strategy: "Documentation-only change. Validate every revised command with the served-content guard and preserve a source-linked boundary note. Do not add a source-string assertion."

existing_issue: "none found by GitHub issue search on 2026-08-07"

existing_pr: "none found by GitHub issue/PR search on 2026-08-07"

duplicate_check: "Searched repository issues for knowledge/rules + dry-plan and policy filters + business rules; both returned zero results."

confidence: verified

estimated_scope: small

recommended_action: implement
```

## Candidate 002: Close or document the served-content memory-flag gap

```yaml
title: "Remove the stale memory-flag skip from the served-content guard"

subsystem: "agent skills / executable documentation / CLI"

classification: test

learning_value:
  score: 5
  explanation: "Shows how package extras, CLI registration, documentation scanning, and CI environment design interact."

user_impact: "A future bundled skill can ship an invalid wren memory flag while the general served-content guard remains green. Current bundled content is clean when the skip is disabled."

observed_failure: "The current guard returns no findings for an injected `wren memory recall --definitely-invalid value`, even though COMMANDS['memory recall'] contains the real --query/--limit/--output/--path/--datasource flags."

reproduction: "experiments/04-served-content-guard/run.py against upstream 9a0f032"

source_trace: "core/wren/tests/unit/test_served_content_guard.py::_SKIP_FLAG_VALIDATION_FOR_GROUPS and _findings; core/wren/src/wren/memory/cli.py; core/wren/src/wren/cli.py"

suspected_root_cause: "The guard retains assumptions from the older conditionally registered memory CLI. Current cli.py always registers memory_app and imports heavy dependencies lazily, so the manual allow-list and skip are stale."

possible_fix: "Delete the manual memory subcommand allow-list and _SKIP_FLAG_VALIDATION_FOR_GROUPS branch; assert real memory flags are loaded; add an invalid-memory-flag mutation test."

test_strategy: "Prepared patch adds a mutation-style invalid-memory-flag test and command-tree assertions. The complete current served corpus has zero findings with memory validation enabled. Focused result: 5 passed; Ruff clean."

existing_issue: "not identified"

existing_pr: "PR #2329 introduced and hardened the generic served-content guard. No issue or PR specifically closing the intentional memory-flag skip was found."

duplicate_check: "GitHub searches on 2026-08-07 found #2329 as the guard's origin, zero matching issues, and no PR targeting memory-flag validation. Repeat immediately before implementation."

confidence: verified

estimated_scope: small

recommended_action: implement
```

## Quality Gate

A new candidate must include every YAML field above. If the failure cannot be
reproduced on the current pin, set `confidence: hypothesis` and do not propose a PR.
