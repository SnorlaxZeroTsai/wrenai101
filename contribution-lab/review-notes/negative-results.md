# Negative Results And Open Questions

## RLAC predicate on a CLAC-denied column

Commit/environment:

- source pin: `9a0f032`
- runtime: locked `wren-core-py 0.7.3`

Probe:

- RLAC condition uses `customer.c_name = @session_user`;
- the same `c_name` column is denied by CLAC for `session_level=2`;
- both properties are active;
- query is `SELECT * FROM customer`.

Observed:

```text
Permission Denied: Access denied to column "customer"."c_name":
violates access control rule "c_name_access"
```

The canonical upstream tests cover RLAC injection and CLAC wildcard pruning
independently. They do not establish the intended precedence for this combined
policy case.

Classification: open question, not a bug.

Before promotion:

1. inspect access-control design history and related issues;
2. determine whether fail-closed is intentional;
3. add a minimal local Rust/PyO3 test against source, not only the published wheel;
4. search duplicate issues/PRs;
5. identify real user impact and expected policy semantics.

## Raw MDL converter non-mapping entry

Commit: `9a0f032`.

Probe:

```python
convert_mdl_to_project({"models": [42]})
```

Observed: Python `TypeError: argument of type 'int' is not iterable`.

Classification: current error-message edge, not a new candidate.

Reason:

- PR #2567 already proposed a broad guard and was closed after maintainer review;
- the real multi-consumer v1 loader defect was split to issue #2597 and fixed by
  merged PR #2604;
- maintainer explicitly classified the remaining raw-converter behavior as a
  legitimate but smaller message improvement;
- no additional impact beyond that reviewed scope was found.

The behavior remains in
[`experiments/07-validation-boundaries`](../../experiments/07-validation-boundaries/)
so future drift is visible without resubmitting the rejected scope.
