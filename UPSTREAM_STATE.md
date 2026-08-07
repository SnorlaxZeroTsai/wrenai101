# Upstream State

## Current Pin

| Field | Value |
|---|---|
| Repository | `Canner/WrenAI` |
| Branch | `main` |
| Commit | `9a0f0324307442cb523b43838f391add328b78f9` |
| Commit date | 2026-08-07 |
| Subject | `refactor(mssql): strip trailing semicolon on unlimited query path for connector consistency (#2633)` |
| Review date | 2026-08-07 |
| Working clone | `.wrenai-src/` |

Previous repository snapshot: `a8a7519` on 2026-07-09.

All "current" claims in the new fundamentals and contribution guides refer to the
current pin unless another commit is named.

## Important Changes Since The Previous Review

- `wrenai` is now `0.13.2`.
- PR #2565 fixed the guided ask template's invalid `wren memory recall --nl`
  instruction and added a behavior-level CLI regression test.
- PR #2602 added the root Contribution Bar, PR template guidance, root
  `AGENTS.md`, and explicit validation-boundary rules.
- `get_session_context` now uses a bounded `@lru_cache(maxsize=32)` because the
  effective manifest is part of the cache key.
- The served-content guard scans packaged skills, ask templates, and the discovery
  stub against the real command tree. It still contains a historical memory
  allow-list/flag skip, even though current `cli.py` always registers the lightweight
  memory group and exposes its real flags without optional ML dependencies.
- Project layout v5 separates version-controlled `knowledge/rules/` and
  `knowledge/sql/` from the derived `.wren/memory/` index.
- PR #2604 fixed the reachable legacy-v1 non-mapping view defect at
  `_load_views_v1`, after PR #2567 was rejected for guarding only one consumer.

## Chapters Possibly Affected

| Area | Status at current pin |
|---|---|
| `deep-dives/text2sql.md` | Core boundary remains valid; old line numbers need symbol-based refresh |
| `deep-dives/large-result-handling.md` | Revalidated selectively; connector behavior can drift |
| `deep-dives/data-isolation.md` | Access-control primitives still exist; identity integration claims require deployment-specific review |
| `deep-dives/security-governance.md` | `strict_mode` and policy path remain; wording about rules is corrected in fundamentals |
| `deep-dives/comparison.md` | Historical market comparison; external products require a fresh review before reuse |
| `deep-dives/legacy-v1-architecture.md` | Historical explanation, not current implementation guidance |

## New Architecture Notes

- Skills use progressive disclosure: a small repository-level discovery stub points
  to CLI-served skill content packaged in the installed wheel.
- Memory has two durable-source paths: `knowledge/sql/*.md` for confirmed NL-SQL
  pairs and MDL plus rules for schema context. LanceDB is a derived optional index.
- The Python planner extracts a query-scoped manifest before creating/reusing a
  PyO3 `SessionContext`.
- Wren-core uses DataFusion 53 and owns semantic analysis, relationship expansion,
  calculated fields, and access-control primitives.

## New Contribution Rules

The current root Contribution Bar requires:

- an observed external failure or clearly measured non-bug change;
- proof that the failing state reaches the changed code;
- honest `fix` / `refactor` / `test` / `docs` classification;
- behavior-level tests that CI actually executes;
- duplicate checks and one cohesive scope;
- rebase and semantic revalidation before review.

PR #2602's review is itself instructive: a proposed validation example was revised
twice after tracing callers showed the apparent raw boundary was already sanitized.

## Representative Merged PR Sample

Reviewed 18 non-bot merged PRs:

`#2522`, `#2525`, `#2526`, `#2533`, `#2565`, `#2570`, `#2576`, `#2577`,
`#2580`, `#2582`, `#2586`, `#2602`, `#2603`, `#2604`, `#2605`, `#2612`,
`#2619`, `#2628`.

See `docs/contributing/02-merged-pr-patterns.md`.

## Open Questions

- Should the served-content guard remove its now-stale memory allow-list/skip?
  The prepared candidate patch does so and passes the focused suite.
- Should `docs/core/concepts/correctness.md` explicitly separate agent-applied
  business rules from engine-enforced MDL access control?
- Experiment 09 confirms planner and connector `WrenError` structure inside
  `WrenEngine`; which fields survive MCP/SDK serialization remains open.
- How should CJK-heavy schema descriptions tune the fixed 30,000-character switch
  between full context and embedding search?

## Refresh Procedure

1. Fetch current `main` and record the new commit.
2. Inspect changed files since this pin.
3. Map changes to the table above.
4. Rerun affected experiments.
5. Update this file before changing chapter conclusions.
