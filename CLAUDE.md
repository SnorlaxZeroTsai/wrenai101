# WrenAI 101 Repository Instructions

This is a long-running source-based learning and contribution project for
`Canner/WrenAI`, not a one-time product evaluation.

## Permanent Rules

1. Use current upstream source over marketing copy.
2. Pin important findings to an upstream commit, file, and symbol.
3. Label claims as observed, reproduced, verified, historical, or hypothesis.
4. Update `UPSTREAM_STATE.md` whenever the reviewed upstream commit changes.
5. Preserve useful existing deep-dive research; mark stale snapshots instead of
   silently presenting them as current.
6. Prefer a runnable experiment before a behavioral conclusion.
7. Never manufacture bugs from TODOs or hypothetical malformed states.
8. Trace reachability and existing validation before proposing a guard.
9. Follow upstream's Contribution Bar and module-level instructions.
10. Update `CONTRIBUTION_BACKLOG.md` only after reproduction and duplicate checks.
11. Tests must exercise behavior or a public interface, not just inspect source text.
12. Do not open issues, push upstream branches, submit PRs, or post comments without
    explicit user instruction.

## Working Upstream

- Clone: `/home/kasm-user/wrenai101/.wrenai-src`
- Reviewed commit: `9a0f0324307442cb523b43838f391add328b78f9`
- State record: `UPSTREAM_STATE.md`

Before source work, read upstream root `AGENTS.md`, `CONTRIBUTING.md`,
`.claude/CLAUDE.md`, and the relevant module-level `.claude/CLAUDE.md`.

## Evidence Format

For each important conclusion record:

```text
Claim
Evidence type
Upstream commit
Source path and symbol
Reproduction or test
Falsifier / drift trigger
```

Candidate contributions must use the schema in `CONTRIBUTION_BACKLOG.md`.
