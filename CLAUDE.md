# WrenAI 101 — 學習專案

深挖 WrenAI(開源 GenBI 引擎)的 text2SQL、大量結果處理、資料存取隔離、
安全治理四大主題。以原始碼為準,不採信官方行銷式描述。

## 關鍵架構事實(2026-07 clone 驗證)

WrenAI repo 在 **2026-05-07 大改版**:
- `main` = 新的 **agent-native** 架構(Rust 語意引擎 + Python CLI/SDK + 瀏覽器端 GenBI)。
  - `core/wren-core*` = Rust 語意引擎(DataFusion),RLAC/CLAC 在此實作。
  - `core/wren/` = Python CLI/SDK(PyPI `wrenai`),含 `policy.py` SQL firewall、connector 執行。
  - **沒有內建 LLM text2SQL 服務**;由外部 agent(Claude/LangChain SDK)呼叫 CLI。
- `legacy/v1` 分支 = 舊的 **Docker chat-first app**(`wren-ai-service/`),含完整 RAG pipeline
  (retrieval + generation + sql_correction + chart)。已凍結,無新功能/安全修補。

→ 使用者的四大問題橫跨兩個架構,回答時必須分辨「新 main」vs「legacy/v1」。

## 原始碼位置(絕對路徑)
clone 在 `/home/kasm-user/Desktop/wrenai101/.wrenai-src`(main,2026-07-09 HEAD = a8a7519),
legacy 用 `git show FETCH_HEAD:...`(FETCH_HEAD = legacy/v1)。

- RLS/CLS 引擎強制:`core/wren-core/core/src/logical_plan/analyze/access_control.rs`
  (⚠ a8a7519 起 CLAC 雙軌:明確引用 deny、wildcard 靜默剪除 `plan.rs:1049-1067`)
- main 的 agent context 供應鏈:`core/wren/src/wren/memory/`(30K 閾值全量/檢索,
  `schema_indexer.py:36`)、`ask.py`+`ask_templates/`、`skills_content/`
- SDK 護欄(LLM-facing 工具 limit=100/cap 1000/16KB):`sdk/wren-langchain/src/wren_langchain/_tools.py`
- knowledge/rules 只是 prompt 素材、引擎不強制(官方 correctness.md:57 誇大):`context.py::load_rules`
- MDL 型別/access control 定義:`core/wren-core-base/src/mdl/{manifest,cls}.rs`
- SQL policy firewall:`core/wren/src/wren/policy.py`(issue #2409:擋 file reader/SSRF/DoS)
- 查詢執行/連線:`core/wren/src/wren/engine.py` + `connector/*.py`
- CLI:`core/wren/src/wren/cli.py`
- legacy RAG:`wren-ai-service/src/pipelines/{retrieval,generation}/`(在 legacy/v1 branch)
