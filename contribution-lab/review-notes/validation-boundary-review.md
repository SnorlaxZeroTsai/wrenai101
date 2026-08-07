# Validation Boundary Review: PR #2567 to PR #2604

Verified against upstream history and `Canner/WrenAI@9a0f032`.

## Initial proposal

PR #2567 proposed guards for non-dict models/views in both
`convert_mdl_to_project` and `validate_project`.

The observed behaviors were not equivalent:

- some raw converter values produced `TypeError`;
- the string fixture in the proposed test already produced `ValueError`;
- loaded model rows were already filtered before `validate_project`;
- legacy v1 view rows reached four consumers because `_load_views_v1` alone did
  not uphold its `list[dict]` contract.

## Maintainer correction

The maintainer rejected the combined patch because the real shared defect belonged
in `_load_views_v1`, not one consumer. A consumer-only guard would leave build and
migration paths exposed, including a partially applied v1-to-v2 migration.

Issue #2597 captured the reachable defect. PR #2604 then:

1. restored the loader contract once;
2. made `validate_project` report raw bad rows instead of silently dropping them;
3. tested validate, build, JSON build, plan-upgrade, and apply-upgrade through real
   v1 project fixtures;
4. left unrelated raw-converter message cleanup out of scope.

## Generalizable lesson

Before adding validation, identify the earliest layer that has both:

- enough raw context to produce an actionable error; and
- enough ownership to restore the invariant for every consumer.

The right answer can be two coordinated behaviors: sanitize at a shared loader and
report at a user-facing validator. It is rarely "add `isinstance` everywhere."

Reproduce the current matrix with
[`experiments/07-validation-boundaries`](../../experiments/07-validation-boundaries/).
