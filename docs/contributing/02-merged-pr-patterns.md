# 02：從 Merged PR 學 Maintainer 偏好

樣本：current review date 2026-08-07，18 個 recent merged non-bot PR：

`#2522`, `#2525`, `#2526`, `#2533`, `#2565`, `#2570`, `#2576`, `#2577`,
`#2580`, `#2582`, `#2586`, `#2602`, `#2603`, `#2604`, `#2605`, `#2612`,
`#2619`, `#2628`。

這裡不做 release-note 式摘要，而是抽出 accepted change 的形狀。

## Pattern 1：先證明 caller path，再談 guard

### PR #2604

- Problem：legacy v1 hand-written view shape 在 migration 後可形成 malformed state。
- Reproduction：追四個實際 consumers，展示 partial migration 的 failure。
- Scope：在 loader/validator 的 reachable boundary 報錯。
- Test：從真 consumer path 建立 malformed project。
- Review result：明確留下另一個已被前置 invariant 保護的類似 function不改。
- Lesson：相似 code shape 不等於相同 reachability。

### PR #2582

- Problem：external Vercel JSON response 可帶 unexpected shape。
- Scope：在真正 external response boundary validation。
- Lesson：外部系統回傳值不能借用內部 typed invariant。

### PR #2580

- Problem：import path 驗證若晚於 `--force` cleanup，bad input 可能先觸發 destructive
  local action。
- Scope：把 validation 移到 destructive action 前。
- Lesson：edge validation 的順序也是 behavior contract。

## Pattern 2：red/green control 比 assertion 數量重要

### PR #2565

- Problem：guided output 生成不存在的 `memory recall --nl` option。
- Reproduction：render output，抽 command，real CLI invocation exit 2。
- Scope：改為 `-q`，不處理同 issue 的 memory-fetch enhancement。
- Test：執行 public command，而不是檢查 template source。
- Review change：maintainer 要求用 `-q` 與其他 skill examples 一致。
- Why accepted：old behavior red、new behavior green、scope 可清楚描述。

### PR #2619

- Problem：shared analyzer cycle stack 在 concurrent use 下產生 spurious cycle errors。
- Reproduction：8 threads x 50 iterations 的 stress probe。
- Test：保留 genuine cycle detection，同時驗證 concurrent false positive 消失。
- Review change：用 type-level choice (`RefCell`, therefore `!Sync`) 編碼 invariant，
  並改善 error propagation。
- Lesson：concurrency fix 要同時證明 false positive 被移除、true positive 仍存在。

### PR #2603

- Problem：Snowflake test mock 讓 11 個 tests 沒進 test body。
- Reproduction：確認 patched call path 沒被 production code 使用。
- Scope：修 test harness，並更新它隨後暴露的 stale assertion。
- Lesson：green test 若沒有執行 target behavior，保護力是零。

## Pattern 3：maintainer 會用資料推翻自己的第一直覺

### PR #2628

- Problem：query-scoped manifest 是 session-cache key，unbounded cache 隨 table
  subset 組合成長。
- Reproduction：production key path + old decorator negative control。
- Initial review：討論 cache size 32 或 128。
- Evidence：作者量測 extraction/session construction 約毫秒級，而 entry memory
  約數百 KiB；maintainer 根據資料撤回較大 cache 建議。
- Test：eviction 與 bounded behavior。
- Lesson：review comment 不是不可挑戰的規格；可重現量測優先。

### PR #2612

- Classification：誠實標為 refactor，沒有宣稱 user-visible fix。
- Evidence：量 build count，不拿 noisy latency 當唯一證明。
- Review changes：補 SQL snapshots、missing branch coverage、清 stale comments，
  maintainer A/B 多種 query shapes。
- Lesson：refactor 的接受條件是 behavior preservation + mechanical evidence。

## Pattern 4：public behavior 與 reverse assertion

### PR #2525

- Problem：nested secret values 在 CLI output 中可能未遮罩。
- Reproduction：經 public CLI output 走真 supported shape。
- Test：不只 assert secret 被 mask，也 assert相似 non-secret text 沒被 over-mask。
- Lesson：security tests 要包含「擋該擋的」與「保留不該擋的」。

### PR #2570

- Problem：row conversion skip 可能靜默隱藏 corruption。
- Scope：區分合法 `None` padding 與 malformed row，限制 diagnostic volume。
- Review effect：錯誤訊息與 strict behavior 更精確。
- Lesson：fail loudly 仍要 bounded，否則 diagnostics 自己成為 failure。

### PR #2526

- Problem：MCP fallback query path 的 row-cap behavior 與 sibling path 不一致。
- Reproduction：追到可達 exception/fallback path。
- Scope：修一個 observed asymmetry，明確留下相鄰 enhancement out of scope。
- CI：使用 dedicated MCP path。
- Lesson：fallback 也是 public contract，不能只測 happy path。

## Pattern 5：negative result 也能產生高價值 follow-up

### PR #2576

- Work：以 tests 定義 physical table visibility contract。
- Result：原假設中的問題不完全成立，但 test 研究暴露另一個 serialization defect。
- Follow-up：真正 defect 在 PR #2577 修正。
- Lesson：不要硬把調查結果包裝成原先想像的 bug；讓證據改變 scope。

### PR #2577

- Problem：execution stream schema serialization 錯誤。
- Scope：修 observed contract。
- Follow-up：maintainer 另開 #2599 追更廣的 type gap。
- Lesson：可 merge 的 smallest fix 與 architecture debt 可以分開追蹤。

## Pattern 6：malformed input changes 需要一致 error policy

PR #2522、#2533、#2586、#2605 都觸及 malformed collection/model/memory shapes。
共同方向是：

- `None` / missing 是否代表 empty 要明確；
- present-but-wrong-type 不應靜默當 empty；
- error 要指出 entity 與 field；
- CLI 要把 `ValueError` 轉成 user-facing failure；
- 同 module 的 sibling collection 應採一致 policy。

但這不表示「看到任何 `.get(..., [])` 就補 guard」。PR #2602 之後的規則要求先
證明 raw/malformed value 能到達該 function。

## Recurring maintainer preferences

1. **Public interface evidence**：CLI/API/real planner 優先於 source-string assertion。
2. **Independent verification**：maintainer 會自行跑 old/new、A/B 或不同 query shape。
3. **Scope statement**：清楚寫 out-of-scope，反而提高可 review 性。
4. **Invariant preservation**：fix false failure 時不能破壞 real failure detection。
5. **Measured trade-off**：cache size、performance、diagnostic cap 用數據談。
6. **Error locality**：在最早有足夠 context 的 reachable edge 報錯。
7. **CI realism**：optional feature、mock、path filter 都是 test design 一部分。
8. **Review-driven revision**：accepted PR 常在 review 中增加 tests、改 classification
   或縮 scope；初版 diff 不是 final design。

## 如何使用這份樣本

找到候選問題後，先找樣本中最接近的 review pattern：

- validation candidate -> #2604 / #2582 / #2602；
- executable docs -> #2565 / #2603；
- concurrency/cache -> #2619 / #2628；
- security/error output -> #2525 / #2570；
- fallback/integration -> #2526；
- negative result -> #2576 / #2577。

模仿的是 evidence shape，不是複製 patch style。
