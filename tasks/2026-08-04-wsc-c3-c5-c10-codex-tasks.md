---
status: current
type: task
owner: claude
created: 2026-08-04
last_reviewed: 2026-08-04
expires: none
superseded_by: null
---

# WS-C 部分授權：C3 / C5 / C10 — Codex tasks

**使用者授權 2026-08-04：「先授權 C3+C5+C10」。**
WS-C 其餘八項（C1、C2、C4、C6、C7、C8、C9、C11）與 F2 **仍未授權**，不得順手一起修。

授權理由（供 Codex 判斷邊界）：這三項是**下單本身的正確性**缺陷，Binance/OKX Demo
在 2026-08-02 已經走過真實下單往返，所以現在就踩得到。其餘各項是停損作動與長跑穩定性
—— 沒有常駐 live/paper 就踩不到，留待要開常駐的前一步再處理。

來源：`tasks/2026-08-03-project-optimization-codex-plan.md` WS-C 表格與「WS-C 通則」。
通則全數適用，特別是：**不得宣稱 live/demo/shadow 就緒**。

## 開工前

行號是 2026-08-03 對照 `6bdafa0` 驗的，之後又有 `181f82b`/`8dd88ab`/`081451b`/
`c9fa77b`/`dc1383d`。**動手前先重新定位符號，不要照行號盲改。**

三項各自一個 commit、各自一份 Change Manifest（`docs/CHANGE_MANIFEST_TEMPLATE.md`）
＋ `python scripts/docs/check_doc_impact.py --strict`。依 C5 → C3 → C10 的順序做。

---

## C5（先做）— `ct_val` fallback 捏造，下單量錯 10 倍

- 位置：`src/okx_quant/api/engine.py`（原 121-126）、
  `src/okx_quant/portfolio/portfolio_manager.py`（原 349）
- 問題：`get_instruments` 失敗時捏造 `ctVal = 0.01`。ETH 實際是 **0.1** →
  下單量錯 10 倍、notional 低估 10 倍，而且繞過了原本會拒絕 fallback 的守衛。
- 修法：**fail closed**。規格抓不到就中止下單，不要猜。移除 BTC/ETH 特例值。
- **重用既有機制**：P0 硬化（F32/F37/I34）已經有一個 finite-positive `ct_val <= 1e7`
  驗證器，在 DB / registry / caller-spec / fill 邊界都接上了。這裡走同一個驗證器，
  **不要新寫一套平行的檢查**。缺的是「取不到規格時不得捏造預設值」這一段。
- 守護測試：`get_instruments` 拋錯 → 斷言**沒有任何下單呼叫發生**，且錯誤明確；
  另加一個測試斷言 ETH 的 `ctVal` 永遠不會是 0.01。

## C3 — `reduceOnly` 沒送到交易所，RiskGuard 卻因它放行

- 位置：`src/okx_quant/execution/broker.py`（原 88-97）
- 問題：RiskGuard 因為訂單標記 reduce-only 而放行 kill switch / fat-finger /
  倉位上限檢查，但 `place_order` 根本沒把 `reduceOnly` 送給 OKX →
  一張「只減倉」的單可能實際開倉甚至翻倉，而且是在風控已經放行的狀態下。
- 修法：`place_order` 實際帶上 `reduceOnly="true"`（以及對應的 `posSide`）。
- 注意：paper-demo 批次 `1992ac2` 已經改過這個檔案（巢狀 `sCode` 驗證、`tag` 淨化、
  價格 tick 對齊、SPOT `tdMode=cash`）—— **不要重做那些**。
- 守護測試：斷言送出的 kwargs 確實含 `reduceOnly` 旗標；再加一個測試斷言
  「RiskGuard 放行 reduce-only」與「旗標實際送出」兩者綁在一起，
  任一缺失即失敗。

## C10 — mid 取自原始 books delta 而非維護中的訂單簿

- 位置：`src/okx_quant/portfolio/portfolio_manager.py`（原 53-54）、
  `src/okx_quant/execution/execution_handler.py`（原 49）、
  `src/okx_quant/api/engine.py`（原 300）
- 問題：三個 consumer 直接取 `books` delta 的 `bids[0][0]`，那可能是深層價位或
  剛被移除的價位 → 權益瞬間爆量或歸零 → 誤觸停損。
- 修法：三處改用 `src/okx_quant/execution/okx_book.py` 既有的 `mid()`（原 :122）／
  `best_bid()`（:108）／`best_ask()`（:115）。這個檔案維護良好但沒人用。
- 守護測試：餵一個**只更新深層價位**的 delta，斷言 mid 不變；
  再餵一個移除 best bid 的 delta，斷言 mid 反映新的 best bid 而非被移除的價位。

---

## PERMITTED FILES

- `src/okx_quant/execution/broker.py`（C3）
- `src/okx_quant/api/engine.py`（C5、C10）
- `src/okx_quant/portfolio/portfolio_manager.py`（C5、C10）
- `src/okx_quant/execution/execution_handler.py`（C10）
- `tests/unit/` 下對應的守護測試
- `docs/FAILURE_MODES.md`、`docs/INVARIANTS.md`、`docs/DOMAIN_RULES.md`
- `docs/change_manifests/2026-08-04-{c5-ctval-fail-closed,c3-reduce-only,c10-book-mid}.md`
- `docs/AI_HANDOFF.md`、`docs/CURRENT_STATE.md`、`config/workstreams.yaml`（收尾）

## FORBIDDEN

- WS-C 其餘八項與 F2 涉及的任何行為改動：`risk_guard.py` 的停損邏輯、
  `circuit_breaker.py`、`market_data_handler.py` 的連線管理、`positions.py` 的對帳、
  `rate_limiter.py`。**讀可以，改不行。**
- `config/risk.yaml`、`config/settings.yaml` 的 mode
- `src/okx_quant/strategies/`、`signals/`
- 既有的 `results/**` artifact

SCOPE LIMIT: 只修 C3/C5/C10 描述的缺陷。不順手重構相鄰程式碼、不改錯誤訊息、
不重命名變數，除非它就是缺陷本身。

## REQUIRED ON COMPLETION（每項各一次）

- `git diff --stat`
- `python -m pytest <該項的守護測試> -v` 尾段
- `python -m pytest tests/unit -q` 尾段（確認沒打壞既有 1120 測試）
- `ruff check <改動檔案>`
- `python scripts/docs/check_doc_impact.py --strict`
- Change Manifest 路徑

## ACCEPTANCE CRITERIA（binary）

- [ ] C5：`get_instruments` 失敗時**沒有任何下單呼叫**發生；`ctVal` 的 0.01 特例值
      已從程式碼中消失；走既有 `ct_val` 驗證器而非新寫的平行檢查
- [ ] C3：送交易所的 payload 含 `reduceOnly`；有測試把「RiskGuard 放行」與
      「旗標送出」綁在一起
- [ ] C10：三個 consumer 都不再直接索引原始 books delta；深層-only 更新的回歸測試通過
- [ ] 三份 Change Manifest 存在，`docs-impact --strict` 通過
- [ ] `docs/FAILURE_MODES.md` 與 `docs/INVARIANTS.md` 各有對應新增
- [ ] 全單元測試無退化
- [ ] diff 不含任何 WS-C 未授權項目所屬的行為改動
- [ ] 回報中**沒有**任何 live / demo / shadow 就緒的宣稱

REPORT: 三項各自的變更檔案、測試輸出尾段、Change Manifest 路徑、
做過的假設、任何 UNCONFIRMED 或跳過的項目。
