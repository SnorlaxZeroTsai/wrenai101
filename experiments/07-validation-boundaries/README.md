# 07：Validation Boundaries

## Question

同一個 non-mapping MDL value 從 legacy project YAML、raw import JSON 與 PyO3
manifest 入口進入時，分別在哪一層被拒絕？

## Hypothesis

current v1 YAML loader 會恢復 `list[dict]` invariant，validator 仍向使用者回報每個
bad row；raw `convert_mdl_to_project` 在 Rust 前可能產生 Python `TypeError`；
直接進 `ManifestExtractor` 的 malformed manifest 由 Rust serde 拒絕。

## Setup

script 建立含 `null`、string 與一個 valid view 的 schema-v1 project，接著：

1. 執行 `validate_project` 與 `build_json`；
2. 把 integer model 傳給 raw MDL converter；
3. 把同類 malformed manifest 傳給 `ManifestExtractor`。

## Command

```bash
$WREN_PYTHON experiments/07-validation-boundaries/run.py
```

## Observed result

在 `9a0f032`：

```text
views.yml > views[0]: ... NoneType
views.yml > views[1]: ... str
built-views: ['summary']
raw-converter-error: TypeError ... not iterable
rust-serde-error: ... Serde JSON error: invalid type ...
```

v1 consumer crash 已由 issue #2597 / PR #2604 修復。較早的 PR #2567 同時修改
loader consumer 與 raw converter；maintainer 因 guard 放錯層而拒絕該版本，並把
real loader defect 改在共同 boundary。raw converter 的 `TypeError` 被明確分類為
可改善的 error message，而不是已證明的資料毀損 bug。

## Source explanation

- `_load_views_v1` 過濾 non-mapping rows，維持 annotated return contract；
- `validate_project` 另讀 raw v1 `views.yml`，因此不會 silent drop user mistake；
- `convert_mdl_to_project` 是 `wren context init --from-mdl` 的 raw JSON edge，
  目前在 membership test 前沒有 mapping guard；
- `ManifestExtractor` 建構時已進 Rust serde，成功後 downstream 可依賴 typed
  `Manifest`。

## Conclusion

「validate once, at the edge」不代表所有入口共用一個 validator。共同 loader
應修共同 invariant；raw converter 可自行改善訊息；typed Rust value 之後不應再
到處猜 nested item 可能是 integer。這個 probe 不建立新 candidate，因 real v1
defect 已修，raw-converter scope 也已有具體 maintainer review。

## What could falsify this conclusion

raw converter 新增 mapping validation、project importer 改為先經 Rust serde、
v1 loader contract 改變，或 `ManifestExtractor` 不再在 construction 時 deserialize。
