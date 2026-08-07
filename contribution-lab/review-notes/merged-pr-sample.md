# Merged PR Evidence Ledger

Review date: 2026-08-07.

Sample:

```text
#2522 #2525 #2526 #2533 #2565 #2570 #2576 #2577 #2580
#2582 #2586 #2602 #2603 #2604 #2605 #2612 #2619 #2628
```

Selection favored context, memory, validation, semantic planning, MCP, security,
agent-facing behavior, and test quality. Bot-only dependency PRs and
connector-only changes without reusable architecture lessons were excluded.

This ledger preserves the requested evidence fields for every sampled PR. The
pattern synthesis is in `docs/contributing/02-merged-pr-patterns.md`.

## #2522: Pydantic list-model tolerance

- **Problem:** `list_models` assumed every manifest row was a named mapping and
  could raise `AttributeError` on partial/malformed input.
- **Reproduction:** an in-process SDK fixture mixed non-dict, nameless, and valid
  models.
- **Scope:** Pydantic SDK runtime only; skip invalid rows and normalize nested
  columns/properties.
- **Test strategy:** behavior test invokes the tool runtime and checks the valid
  model remains with a deterministic column count.
- **Maintainer feedback:** approved; no substantive public blocking comment.
- **Changed during review:** no substantive revision recorded in the sampled
  public review data.
- **Why accepted:** narrow SDK behavior, concrete fixture, and a regression test
  rather than a broad core manifest-policy change.
- **Generalizable lesson:** validate at the consumer boundary actually receiving
  untrusted/partial data; do not infer a repository-wide invariant from one SDK.

## #2525: recursive secret masking

- **Problem:** `profile debug` masked top-level secrets but printed supported
  nested `kwargs`/`settings` secrets in plaintext.
- **Reproduction:** real profile-debug output showed top-level password masked and
  nested password/token exposed.
- **Scope:** make masking traversal match the already-recursive environment
  expansion shape.
- **Test strategy:** public CLI output assertions cover dicts/lists, secrets, and
  reverse assertions against over-masking benign values.
- **Maintainer feedback:** review identified newly reachable non-string mapping
  keys in recursive traversal.
- **Changed during review:** sensitive-key handling and annotations were widened
  safely without treating numeric keys themselves as secret.
- **Why accepted:** high-impact reachable disclosure, precise source trace, and
  both positive and negative security assertions.
- **Generalizable lesson:** security predicates and traversal depth must implement
  the same supported data shape.

## #2526: MCP fallback row cap

- **Problem:** `list_stored_queries` capped the LanceDB path but returned the full
  Markdown corpus after fallback.
- **Reproduction:** trace showed the broad `except Exception` makes fallback
  reachable even with the memory extra installed.
- **Scope:** apply the existing `MAX_ROW_LIMIT` default to one sibling path.
- **Test strategy:** exercise the MCP fallback with omitted and explicit limits.
- **Maintainer feedback:** approved; no substantive public blocking comment.
- **Changed during review:** no substantive revision recorded.
- **Why accepted:** one handler had two observable paths with an unambiguous
  contract mismatch.
- **Generalizable lesson:** fallback behavior is part of the public resource and
  safety contract.

## #2533: schema-indexer malformed rows

- **Problem:** schema description/extraction crashed when model, relationship, or
  view lists contained non-mapping entries.
- **Reproduction:** direct mixed-row manifest calls aborted instead of producing
  partial schema context.
- **Scope:** skip non-dict/nameless rows, matching existing cube behavior.
- **Test strategy:** behavior tests assert only valid schema records survive.
- **Maintainer feedback:** automated review found the original assertion checked a
  nonexistent `name` key, making it incapable of detecting invalid records.
- **Changed during review:** assertion moved to the real `item_name` output
  contract.
- **Why accepted:** reachable memory-preparation failure plus a corrected
  regression that genuinely failed on bad output.
- **Generalizable lesson:** verify the test's field names against production
  output; a green assertion on `dict.get` can be vacuous.

## #2565: guided recall option

- **Problem:** `wren ask --guided` emitted `wren memory recall --nl`, but recall
  accepted `--query/-q`.
- **Reproduction:** Docker/current-checkout invocation exited with Click usage
  error and confirmed the imported package path.
- **Scope:** fix the recall step only; the issue's memory-fetch enhancement stayed
  out of scope.
- **Test strategy:** render the guided output, extract the emitted command, invoke
  the real CLI, and reject exit code 2.
- **Maintainer feedback:** use `-q` to align the public vocabulary with other
  skills; automated review suggested shell-aware parsing.
- **Changed during review:** final spelling became `-q`; the merged test retained
  its narrow command-execution invariant.
- **Why accepted:** observed public failure, red/green control, current CLI
  execution, and disciplined scope.
- **Generalizable lesson:** test whether served instructions execute, not whether
  a template contains one preferred string.

## #2570: skipped type rows

- **Problem:** CLI type translation reported only a skipped count, hiding whether
  rows were benign `None` padding or corrupt values.
- **Reproduction:** mixed JSON batches showed valid results with opaque row loss.
- **Scope:** keep pure library signatures; add CLI diagnostics, a ten-row cap, and
  `--strict` for non-`None` corruption.
- **Test strategy:** real CLI cases for objects/strings, benign/corrupt rows,
  strict exit status, truncation, and non-array top-level JSON.
- **Maintainer feedback:** requested rejection of non-array JSON before the new
  invariant and stronger coverage of payload types/truncation.
- **Changed during review:** top-level validation and missing negative/truncation
  assertions were added.
- **Why accepted:** diagnostics became actionable without turning benign padding
  into failure or flooding stderr.
- **Generalizable lesson:** strictness needs an input contract and bounded,
  testable diagnostics.

## #2576: physical-table visibility contract

- **Problem:** late table-registration visibility was relied upon but undocumented
  and untested.
- **Reproduction:** register-before-load, register-after-derivation, and
  register-then-reload scenarios exercised real query results.
- **Scope:** tests and docs only; no production behavior change.
- **Test strategy:** Parquet fixtures plus row-level Arrow decoding.
- **Maintainer feedback:** approved; no substantive public blocking comment.
- **Changed during review:** no substantive revision recorded.
- **Why accepted:** it pinned an important consumer contract honestly as `test`,
  and the investigation exposed a separate defect without conflating scopes.
- **Generalizable lesson:** a negative/no-code investigation can create a valuable
  executable contract.

## #2577: Arrow execution schema

- **Problem:** query IPC used logical-plan schema while batches carried physical
  types, corrupting integers and breaking strings.
- **Reproduction:** row decoding under MDL/physical type mismatch; empty and
  non-empty results exposed inconsistent schema risks.
- **Scope:** serialize with `execute_stream()` schema; casting to declared types
  remained out of scope.
- **Test strategy:** row-correctness regression and empty/non-empty schema parity.
- **Maintainer feedback:** accepted and opened follow-up #2599 for the broader
  logical-versus-physical type gap.
- **Changed during review:** follow-up scope was separated rather than added.
- **Why accepted:** direct data-corruption proof and a fix at the stream ownership
  boundary.
- **Generalizable lesson:** fix the proven serialization contract and track wider
  type design separately.

## #2580: import path preflight

- **Problem:** malformed import output paths were detected only after `--force`
  deleted existing project files.
- **Reproduction:** invalid/outside/root-resolving paths caused partial mutation
  before failure.
- **Scope:** validate all paths before mutation and reuse resolved paths.
- **Test strategy:** assert invalid imports leave existing files unchanged.
- **Maintainer feedback:** approved and opened #2630 for the analogous layout
  upgrade path.
- **Changed during review:** adjacent layout-upgrade work stayed a follow-up.
- **Why accepted:** reachable destructive ordering defect with filesystem-state
  regression proof.
- **Generalizable lesson:** validate before irreversible effects; sibling paths
  can be tracked without bloating one PR.

## #2582: Vercel response shape

- **Problem:** deploy assumed `resp.json()` returned an object; arrays or invalid
  JSON failed later with misleading attribute errors.
- **Reproduction:** mocked request responses returned non-JSON and JSON arrays.
- **Scope:** validate status first, then JSON parse and top-level object shape.
- **Test strategy:** HTTP-error precedence, invalid JSON, non-object JSON, and
  success path.
- **Maintainer feedback:** requested import ordering so the new test passed Ruff.
- **Changed during review:** test imports were sorted; behavioral scope stayed
  unchanged.
- **Why accepted:** genuine external boundary, clearer error context, focused
  tests.
- **Generalizable lesson:** external JSON is untyped even after parsing, and
  validation order determines the error users see.

## #2586: nested memory collection shapes

- **Problem:** truthy non-list or non-dict nested schema collections could crash or
  generate invalid records.
- **Reproduction:** malformed models/columns/relationships/views and nested cube
  collections exercised describe/extract paths.
- **Scope:** consistent collection-shape handling inside schema indexing.
- **Test strategy:** assert malformed sentinels are absent, record counts are
  exact, and wrong top-level collection types fail clearly.
- **Maintainer feedback:** requested negative assertions, exact output counts, and
  guards for truthy non-list collections.
- **Changed during review:** tests and implementation expanded from "does not
  crash" to explicit exclusion/error contracts.
- **Why accepted:** behavior became deterministic across sibling collection
  shapes.
- **Generalizable lesson:** no-crash tests are insufficient when silent junk
  output is also wrong.

## #2602: Contribution Bar

- **Problem:** recurring review load from unevidenced fixes, unreachable guards,
  inert tests, duplicate work, and stale CI.
- **Reproduction:** repository review history and incidents #2482/#2598, not a
  product runtime defect.
- **Scope:** root/module instructions and PR template; docs-only.
- **Test strategy:** self-checkable author prompts rather than code tests.
- **Maintainer feedback:** validation-boundary timing and repository/module
  instruction wording were challenged; checkbox attestations were rejected as
  low-signal.
- **Changed during review:** raw-edge example was corrected after caller tracing,
  and the template kept open questions instead of blind checkboxes.
- **Why accepted:** it encoded observed review patterns without pretending to fix
  runtime behavior.
- **Generalizable lesson:** contribution rules themselves must satisfy reachability
  and honest-classification standards.

## #2603: Snowflake test patch target

- **Problem:** 11 connector tests failed before entering their bodies because
  `mock.patch` targeted a nonexistent module attribute.
- **Reproduction:** 11 failed/5 passed; fixing the target exposed a stale
  client-side slicing assertion.
- **Scope:** test harness and assertion only; preserve function-local optional
  driver import.
- **Test strategy:** patch the actual `snowflake.connector.connect`, assert SQL
  limit pushdown, and run all 16 tests.
- **Maintainer feedback:** approved; PR itself noted the file was absent from
  current CI.
- **Changed during review:** no substantive public revision recorded.
- **Why accepted:** it made an inert suite execute real connector behavior and
  honestly documented remaining CI weakness.
- **Generalizable lesson:** tests that never reach their body protect nothing;
  green CI scope must be verified separately.

## #2604: legacy view loader boundary

- **Problem:** `_load_views_v1` returned non-mapping rows to four consumers that
  immediately called mapping methods, including a partially destructive upgrade.
- **Reproduction:** `null`/string entries crashed validate, build, plan, and apply
  paths.
- **Scope:** filter at the shared loader and report malformed entries in
  validation.
- **Test strategy:** exercise every consumer plus valid sibling preservation.
- **Maintainer feedback:** automated review found non-list `views` containers were
  still inconsistent.
- **Changed during review:** added scalar/dict/null container coverage and
  normalized every consumer to empty while validation reports one precise error.
- **Why accepted:** one reachable edge fixed four consumers without downstream
  defensive duplication.
- **Generalizable lesson:** validate once at the shared raw boundary, and test all
  consumers that rely on its return annotation.

## #2605: relationship endpoint type

- **Problem:** non-list `relationship.models` could crash or silently render
  string characters as join endpoints.
- **Reproduction:** `"orders"` became `o -> r`; dict/int inputs raised inconsistent
  errors.
- **Scope:** one helper shared by describe/extract paths.
- **Test strategy:** wrong types, valid list, missing field, and explicit null.
- **Maintainer feedback:** requested `models: None` coverage and the full
  relationship/field/type error contract.
- **Changed during review:** null case and precise error assertions were added.
- **Why accepted:** it prevented silent semantic corruption and matched the
  module's established missing/null policy.
- **Generalizable lesson:** test exact diagnostics when locality is part of the
  proposed fix.

## #2612: aliased scan refactor

- **Problem:** aliased model scans built and discarded a wildcard-expanded
  `ModelPlanNode` before rebuilding it with real required columns.
- **Reproduction:** a test-only production call counter showed two builds on base
  and one on the branch.
- **Scope:** refactor, explicitly no behavior or latency claim.
- **Test strategy:** build-count regression, SQL snapshots, full Rust and
  sqllogictest suites.
- **Maintainer feedback:** independently A/B tested 10-19 query shapes and found
  stale comments, missing branches, and an unreachable old branch.
- **Changed during review:** comments, branch coverage, snapshots, and dead path
  cleanup were revised.
- **Why accepted:** honest classification, measurable mechanical win, and broad
  SQL parity evidence.
- **Generalizable lesson:** refactors need behavior-preservation evidence and
  should measure the claimed effect, not a noisier proxy.

## #2619: RLAC analyzer concurrency

- **Problem:** one analyzer instance shared a mutable cycle-detection stack across
  concurrent optimize calls, causing false cycle errors and risking missed real
  cycles.
- **Reproduction:** one shared context, 8 barrier-started threads x 50 iterations;
  old code failed reliably.
- **Scope:** make cycle state per invocation while preserving recursive cycle
  tracking.
- **Test strategy:** concurrent acyclic stress plus existing real-cycle tests.
- **Maintainer feedback:** independently reproduced; requested contextual error
  propagation and a type (`RefCell`) that encodes non-shared state rather than
  an uncontended `Mutex`.
- **Changed during review:** panic-only assertion became contextual planning error;
  state holder changed to `RefCell`; docs explained borrow lifetime.
- **Why accepted:** red/green concurrency proof and preservation of true-positive
  cycle detection.
- **Generalizable lesson:** use types to state concurrency ownership and test both
  false-positive removal and true-positive preservation.

## #2628: bounded session cache

- **Problem:** `functools.cache` retained one native `SessionContext` for every
  distinct query-scoped manifest tuple.
- **Reproduction:** production key path grew `currsize` to N with `maxsize=None`;
  old decorator failed eviction tests.
- **Scope:** `lru_cache(maxsize=32)` with no configurability claim.
- **Test strategy:** bound, recency refresh, identity survival, and eviction/rebuild
  through the decorated production function.
- **Maintainer feedback:** suggested considering a larger cache, then independently
  measured real binding cost and memory.
- **Changed during review:** 200/800-model and real-binding measurements showed
  extraction remained cheap while retained memory dominated; reviewer withdrew
  the larger-size suggestion.
- **Why accepted:** bounded failure mode, genuine old-code red tests, and measured
  trade-off.
- **Generalizable lesson:** data can and should overturn reviewer intuition,
  including in the contributor's favor.

## Cross-sample review questions

- Did the author show the state is reachable from a public/raw input?
- Is there an old-behavior red control?
- Does the test invoke behavior or only inspect implementation text?
- Which CI job executes the test with required extras?
- Did review change scope, classification, test shape, or error contract?
- Was a reviewer intuition revised after measurement?
- What adjacent work was explicitly left out?
