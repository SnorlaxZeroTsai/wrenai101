# 06：Agent Skills 與 Progressive Disclosure

驗證基準：`Canner/WrenAI@9a0f032`

## 問題

把所有 workflow、references、connector notes 與 examples 永久塞進 agent prompt，
會造成：

- context cost 固定且持續增加；
- 不相關指令干擾當前任務；
- installed CLI 已更新，但複製在 agent directory 的大份 skill 還停在舊版本；
- command rename 後，文件例子無法跟 package release 一起修正。

current WrenAI 用 progressive disclosure 把「發現」與「完整操作內容」分開。

## Delivery path

```text
Agent session
    |
    v
small discovery stub
skills/wren/SKILL.md
    |
    | wren skills list
    | wren skills get <name>
    v
main served workflow
core/wren/src/wren/skills_content/<name>/SKILL.md
    |
    +--> --full: sorted references/*.md
    +--> --script <name>: one bundled script
```

第一層只教 agent 如何找到 current capabilities。第二層才載入正在使用的 skill，
第三層只在需要時載入 reference 或 script。

## 為什麼內容由 CLI serve

`core/wren/src/wren/skills_delivery.py::_content_root` 使用
`importlib.resources.files("wren") / "skills_content"`。wheel build artifacts 明確
包含：

- `src/wren/skills_content/**/*.md`
- `src/wren/skills_content/**/*.py`
- `src/wren/ask_templates/*.tmpl`

因此 skill content 跟 installed `wrenai` version 一起發布。agent 不必依賴一份
可能長期未更新的 copied bundle。

## Main、reference、script 的成本

`get_skill(name, full=False)` 只回 `SKILL.md`。

`full=True` 才依 filename 排序，附加所有 `references/*.md`。`get_script` 只回指定
script。這讓 agent 可以：

1. 先用 summary 選 skill；
2. 只載主流程；
3. 遇到特定 dialect/edge case 再讀 reference；
4. 需要 executable helper 時再取 script。

這是 agent knowledge 的 lazy loading。

## Executable documentation guard

`core/wren/tests/unit/test_served_content_guard.py`：

1. 從真正的 Typer app 建 Click command tree；
2. 掃描 packaged skills、ask templates、discovery stub；
3. 抽出 `wren ...` invocations；
4. 驗證 command path；
5. 對可 introspect command 驗證 long flags；
6. 設定至少 200 invocations 的 scanner floor，避免 regex 靜默失效。

這比 source-string test 強，因為 command tree 來自真正 public interface。

## 已確認的 guard boundary

guard 仍保留舊設計：

- hard-code memory subcommand names；
- 將 `_SKIP_FLAG_VALIDATION_FOR_GROUPS = {"memory"}`；
- 抓得到 `wren memory typo`；
- 抓不到 `wren memory recall --nonexistent-flag`。

但 current `cli.py` 已明確永遠註冊 memory group，並把 LanceDB/ML imports 延後到
需要的 command 內。real command tree 已包含 recall/fetch flags，所以 skip 的
dependency 理由已失效。

實驗注入 invalid memory flag，`_findings()` 回空；同一 invalid flag 放在
`wren skills get` 則被報告。見
[`experiments/04-served-content-guard`](../../experiments/04-served-content-guard/)。

進一步把 skip 設為空後：

- current served corpus 有零 findings；
- invalid memory flag 會被抓到；
- focused candidate patch `5 passed` 且 Ruff clean。

這個觀察的正確分類是：

> 已驗證的 stale test-harness exception；current bundled content 沒有壞 memory flag。

prepared fix 直接移除 manual allow-list 與 skip，並以 command-tree assertions 加
invalid-memory-flag regression 鎖住 invariant。

## Guided recall case

舊 guided template 曾輸出 `wren memory recall --nl`，但 public option 是
`--query/-q`。PR #2565 不只換 flag，也 render guided workflow、抽出 command、
用真 CLI runner 執行並確認不是 usage error。

這個 regression test 補的是「agent 收到的 instruction 必須可執行」，而不只是
template 包含某字串。完整 postmortem：
[`contribution-lab/cases/guided-recall-flag`](../../contribution-lab/cases/guided-recall-flag/)。

## Generalizable pattern

Progressive disclosure 適合任何 agent tool：

```text
stable discovery vocabulary
-> version-coupled served workflow
-> on-demand deep references
-> executable validation against the real tool interface
```

它同時控制 context cost 與 documentation drift，但 guard 本身仍必須與 optional
feature registration、CI matrix 一起設計。

## Source anchors

- `skills/wren/SKILL.md`
- `skills/AUTHORING.md`
- `core/wren/src/wren/skills_delivery.py::get_skill`, `get_script`, `list_skills`
- `core/wren/pyproject.toml` wheel artifacts
- `core/wren/src/wren/skills_content/`
- `core/wren/tests/unit/test_served_content_guard.py`
- `core/wren/tests/unit/test_ask_cli.py`

## Falsifier

若 skills 改為 remote registry、stub 內嵌完整內容、package artifacts 不再包含
served content，或 guard 改成完整 optional-extra matrix，本章需更新。
