# Served-content Guard Coverage Matrix

Verified at `Canner/WrenAI@9a0f032`.

| Mutation | Current guard | Interpretation |
|---|---|---|
| Valid `wren skills get usage --full` | pass | expected |
| Unknown subcommand under known group | finding | protected |
| Invalid flag on ordinary command | finding | protected |
| Invalid flag on memory command | no finding | stale explicit skip; candidate 002 |
| Same memory flag with skip removed | finding | real flags are already introspectable |
| Unknown top-level `wren frobnicate` | no finding | treated as possible prose |
| CLI-valid but semantically invalid SQL example | no finding | semantic execution is outside this guard |
| Complete current corpus with memory skip removed | zero findings | candidate patch does not expose existing drift |

## Cross-document drift boundary

The guard catches drift only when it manifests as an invalid recognized CLI command,
subcommand, or long flag. It does not compare narrative claims across documents and
does not execute SQL/MDL examples.

## Unknown top-level commands

The scanner deliberately ignores first tokens outside `_TOP_LEVEL_COMMANDS` because
served prose contains phrases such as "wren engine", "wren project", and "wren SDK".
Current corpus has 26 such regex matches. Treating every one as a command would create
false positives.

A future improvement would need Markdown-aware executable-span parsing before it
could safely reject unknown top-level commands. No current broken top-level command
was found, so this remains a documented limitation rather than a bug candidate.

## Semantic examples

The guard validates CLI shape, not SQL correctness against a project/database. A
separate fixture-driven example suite would own that invariant. No such candidate is
proposed without first identifying a current served example that fails.
