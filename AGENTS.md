# Repository Agent Guide

This repository teaches WrenAI from source and turns architecture learning into
evidence-backed contribution candidates.

## Required Practice

- Read `UPSTREAM_STATE.md` before relying on a source claim.
- Cite the upstream commit, path, and symbol for architecture conclusions.
- Distinguish source observations from runtime observations and hypotheses.
- Keep beginner material in `docs/fundamentals/`; preserve detailed analysis in
  `docs/deep-dives/`.
- Put reproducible probes in `experiments/` with question, hypothesis, setup,
  command, observed result, source explanation, conclusion, and falsifier.
- Apply WrenAI's Contribution Bar: prove the problem, show reachability, classify
  honestly, test behavior, check CI and duplicates, keep one cohesive scope.
- Record negative results. "No reachable bug found" is useful evidence.
- Do not publish anything upstream without explicit user approval.

## Update Loop

```text
pin upstream
-> inspect changed subsystems
-> update UPSTREAM_STATE.md
-> rerun affected experiments
-> revise conclusions
-> update learning and contribution backlogs
```
