# Learning Backlog

Priorities measure architecture value, not ease of writing.

## P0

- [x] **Current architecture map**: establishes ownership across Python, PyO3,
  Rust, skills, SDKs, and connectors; without it every later trace is ambiguous.
- [x] **MDL lifecycle**: explains where semantic facts become deterministic and
  where malformed project input is rejected.
- [x] **Context layer**: prevents collapsing rules, schema, examples, profiles,
  and indexes into the vague label "RAG".
- [x] **Skills delivery**: demonstrates progressive disclosure and executable
  documentation validation.
- [x] **Contribution Bar**: sets the evidence standard for all future candidates.

## P1

- [ ] **Memory internals beyond the public flow**: measure index rebuild behavior,
  stale-hash handling and retrieval quality. Grep fallback durability, same-NL
  update, reset, and bounded recall are covered by experiment 08.
- [ ] **Validation boundaries**: build a boundary matrix for raw JSON, YAML project
  files, OSI/API input, Rust serde, and already-typed manifests. Experiment 07
  covers YAML, raw import JSON, and Rust serde; OSI/API remains.
- [ ] **Error model**: trace `WrenError`, Rust-to-Python conversion, connector errors,
  Typer exits, MCP responses, and what information agents can recover from.
  Experiment 09 covers policy/planning, connector, config, and Typer boundaries;
  Rust conversion plus MCP/SDK serialization remain.
- [ ] **Semantic engine**: follow one relationship and one calculated field through
  DataFusion analyzer rules and generated SQL snapshots.
- [ ] **Access-control execution**: rerun RLAC/CLAC examples on the current Rust
  engine, including quoted identifiers, wildcard projection, and concurrent use.

## P2

- [ ] **MCP integration**: compare in-process MCP tools/resources with direct CLI
  behavior and identify which error and row-limit contracts differ.
- [ ] **LangChain and Pydantic SDKs**: map tool limits, output truncation, and retry
  responsibilities back to the core engine.
- [ ] **Connectors**: study common interface invariants first, then select one native
  and one Ibis-backed connector for contrast.
- [ ] **WASM / GenBI deployment**: understand the browser execution model,
  single-thread constraints, artifact packaging, and security boundary.
- [ ] **Evaluation**: locate current golden-query or SQL logic test coverage and
  determine how context/agent regressions should be measured.

## Selection Rule

Pick the next item by asking:

> Will understanding this subsystem expose a reusable invariant that can be tested?

Do not select work merely because a TODO or small diff is visible.
