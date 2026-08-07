# 05：Context 與 Memory

驗證基準：`Canner/WrenAI@9a0f032`

## 不要把所有資訊都叫 RAG

WrenAI 把「agent 需要知道的東西」依 durability、typed enforcement、retrieval cost
與 consumer 分開。這比單一 vector store 更容易 review、version 與重建。

## Knowledge placement table

| Knowledge type | Storage representation | Runtime retrieval | Consumer | Versioning | Validation |
|---|---|---|---|---|---|
| Physical/semantic schema | project YAML -> `target/mdl.json` | project discovery / `memory fetch` | engine + agent | YAML committed；target derived | Python project checks + Rust serde/analysis |
| Model descriptions / values | MDL properties | full schema description或memory search | agent；部分 engine metadata | with MDL | typed field shape |
| Business rules | `knowledge/rules/*.md` | `wren context instructions`; optional memory index; MCP resource | agent | committed | Markdown/path checks，非 typed policy |
| Confirmed NL-SQL | `knowledge/sql/*.md` | grep recall 或 LanceDB query history | agent | committed | Markdown parser / CLI input |
| Semantic index | `.wren/memory/` LanceDB | vector search | memory commands | derived, rebuildable | hash/dimension/table checks |
| Connection config | `~/.wren/profiles.yml` + env | active profile resolution | CLI/connectors | machine/environment local | Pydantic field registry |
| Workflow procedure | packaged `skills_content` | `wren skills get` | agent | versioned with wheel | served-content tests |
| Deep reference | skill `references/*.md` | `--full` / targeted retrieval | agent when needed | versioned with wheel | package + command guard |

## Rules 的實際 path

`load_rules(project_path)` 合併：

- `knowledge/rules/*.md`；
- legacy `instructions.md`。

Consumers 包括：

- `wren context instructions`；
- memory index 的 `_instructions` auxiliary field；
- MCP instructions resource；
- agent workflow。

一般 `build_manifest` / `build_json` 不呼叫 `load_rules`，因此 rules 不進
`target/mdl.json`。它們是「agent 應套用」的 guidance，不是自動 SQL enforcement。

若 default filter 是安全邊界，只寫 Markdown 不夠；應使用 MDL typed control、
strict/policy layer、database privilege/policy，或 identity-aware gateway。

## Memory 的 durable source

### Query memory

`wren memory store` 將 confirmed NL-to-SQL pair 寫到 `knowledge/sql/*.md`。沒有
memory extra 時，recall 可使用 grep backend 直接讀這些 files。

same-NL store 會更新同一 Markdown file；不同 NL 若 slug collision 才加 suffix。
grep recall 以 token overlap / NL substring 排序，最後套 caller 的 `limit`。
`memory reset` 在 grep mode 不會刪 source。可重跑：
[`experiments/08-memory-recall`](../../experiments/08-memory-recall/)。

### Schema memory

安裝 memory extra 後，`wren memory index`：

1. 讀 compiled manifest；
2. 可把 rules 放在 auxiliary `_instructions`；
3. `extract_schema_items` 產生 model/column/relationship/view/cube records；
4. 建 embeddings 與 LanceDB tables；
5. 載入 `knowledge/sql` pairs。

LanceDB 不是 source of truth。換 embedding model 或 index 損壞時，應由 project
artifacts 重建。

## Full context vs retrieval

`MemoryStore.get_context` 先呼叫 `describe_schema(manifest)`。

```text
len(description) <= 30,000 chars
    -> strategy="full"

len(description) > 30,000 chars
    -> strategy="search"
       + vector query
       + optional item/model filters
```

30K 是 character threshold，不是 tokenizer count。source comment 估英文約 4:1
chars-to-tokens，CJK 約 1.5:1，因此 CJK-heavy schema 會在 token 較高時才達相同
character count；upstream comment 對「sooner」的表述值得另行量測，不應在沒有
實驗前升級成 bug。

可重跑 threshold behavior：
[`experiments/02-context-threshold`](../../experiments/02-context-threshold/)。

## Failure behavior

- grep backend：不用建 schema vector index，但 `memory fetch` 的 semantic schema
  search 需要 memory extra；
- malformed top-level/nested collections：`schema_indexer` 對 non-list shape 拋
  `ValueError`，CLI 轉成 `Malformed manifest`；
- stale schema index：search 會用 manifest hash filter；
- embedding dimension mismatch：store 拒絕混用並要求 reset/restore model；
- empty or missing query knowledge：recall 回 empty，不應發明 example。

## Agent session 的建議順序

```text
first question:
  context instructions
  -> memory fetch
  -> memory recall

every question:
  write MDL SQL
  -> plan/execute
  -> store only after confirmation
```

把未驗證 SQL 存成 confirmed memory，會把一次 hallucination 變成 durable future
context，因此 store 是 review boundary。

## Source anchors

- `core/wren/src/wren/context.py::load_rules`, `build_manifest`
- `core/wren/src/wren/memory/cli.py::index`, `fetch`
- `core/wren/src/wren/memory/schema_indexer.py::SCHEMA_DESCRIBE_THRESHOLD`
- `core/wren/src/wren/memory/store.py::MemoryStore.get_context`
- `core/wren/src/wren/memory/markdown.py`
- `core/wren/src/wren/memory/index_backend.py`

## Falsifier

若 project build 開始嵌入 rules、grep backend 被移除、threshold 改成 tokens，或
LanceDB 成為唯一 durable source，本章需重寫。
