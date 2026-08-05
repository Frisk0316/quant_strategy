---
status: current
type: task
owner: claude
created: 2026-08-05
last_reviewed: 2026-08-05
expires: none
superseded_by: null
---

# H-009 資金費率多空:換倉持倉 log(供工作紀錄頁)— 交付 Codex(2026-08-05)

使用者需求 2026-08-05:公開工作紀錄頁的「資金費率多空策略」卡片要顯示
**每次換倉的結果與做多/做空各幣種的金額**。現行
`backtesting/funding_xs_dispersion_backtest.py` 只輸出報酬序列,沒有持倉 log。

## 前提事實(Codex 不要重新推導)

- 該策略**每週一換倉**(`rebalance == "weekly"`),不是每日;頁面按實際頻率顯示。
- 顯示對象是 E-063 的凍結參數重播:`results/strategy_finding_20260726/
  f_funding_xs_dispersion_retry1/summary.json` 的 `full_sample_best_params`
  (lookback_days=7、quantile=0.2、inverse_vol、max_name_weight=0.1、
  vol_target 0.175 等,31 檔 universe)。
- 頁面端已就緒:`scripts/worklog/snapshot_strategies.py` 會讀
  `<E-063 目錄>/holdings.json`,存在即渲染,不存在則顯示「整備中」。
- **治理邊界**:這是既有凍結參數的 reporting 重播,不是新實驗 —— 不改參數、
  不 grid、不宣稱任何 gate;不得更動既有 summary/checkpoint artifacts,
  不佔用 H-009 重測額度、不新增 EXPERIMENT_REGISTRY 列(在報告中明講這句)。

## Task: 為 funding_xs_dispersion 回測加選配 holdings log

Task: 給既有回測加一個 opt-in 的持倉輸出,並用凍結參數跑一次產出
`holdings.json` 供工作紀錄頁顯示。
Plan source: 本檔
Strategy/spec source: `results/strategy_finding_20260726/f_funding_xs_dispersion_retry1/summary.json`(凍結參數,不得偏離)

### PERMITTED FILES(只能改這些)

- `backtesting/funding_xs_dispersion_backtest.py`(加選配輸出,預設關閉、
  不影響既有輸出與數值)
- `scripts/worklog/build_funding_holdings.py`(新增:以凍結參數呼叫回測、
  寫 holdings.json 的薄包裝)
- `tests/unit/test_funding_holdings_log.py`(新增)
- `results/strategy_finding_20260726/f_funding_xs_dispersion_retry1/holdings.json`
  (新增的產出檔;目錄內其他既有檔案一律不得改動)
- `docs/FEATURE_MAP.md`、`docs/AI_HANDOFF.md`、`docs/CURRENT_STATE.md`(收尾同步)

### FORBIDDEN(不要碰)

- `src/okx_quant/strategies/`、`risk/`、`portfolio/`、`execution/`、`config/`
- 既有 `results/**` 檔案的任何修改(只允許新增上述 holdings.json)
- `docs/EXPERIMENT_REGISTRY.md`、`docs/HYPOTHESIS_LEDGER.md`(不是實驗)
- `scripts/worklog/` 其他檔案、`worklog_page/**`(頁面端已完成)

SCOPE LIMIT: 只做上述內容;回測數值行為零改變(既有測試必須原樣通過)。

### 必要行為

**A. 回測選配輸出**:`holdings_log=True`(或 `--holdings-out`)時,每個
rebalance 日記錄:`date`、`long: {symbol: weight}`、`short: {symbol: weight}`
(權重為佔投組名目的比例,含 inverse_vol 與 max_name_weight 之後的最終權重)、
該持倉期間的 `period_return`。預設關閉時輸出與現狀 byte 級一致。

**B. `build_fundings_holdings` 包裝**:從 E-063 summary 讀凍結參數 → 跑一次 →
寫 `holdings.json`:`{"schema_version": 1, "generated_at": ..., "params_frozen_from":
"E-063", "notional_base_usd": 10000, "rebalances": [{date, long: {SYM: usd},
short: {SYM: usd}, period_return}]}`,金額 = 權重 × notional_base_usd(名目
基準額,只是把比例換成可讀金額;在檔案內明示這是假設名目)。
symbol 顯示名去掉 `-USDT-SWAP` 後綴。

**C. 測試**:fixture 資料跑小型回測,斷言 (1) 預設關閉時輸出不變;
(2) 開啟時每個 rebalance 的 long/short 權重各自加總 ≈ 0.5(dollar-neutral)
且單一幣種權重 ≤ max_name_weight;(3) holdings.json schema 正確。

### REQUIRED ON COMPLETION

- `python -m pytest tests/unit/test_funding_holdings_log.py -v` 與既有
  funding_xs_dispersion 相關測試全綠;`ruff check` 觸及檔案
- 真實產出一次 holdings.json,貼前 30 行
- 跑 `python scripts/worklog/snapshot_strategies.py --out <暫存>`,確認
  `rebalances.available` 不再是 false 且無錯
- 報告中明講:非實驗、未動既有 artifacts、未佔重測額度、無 Change Manifest
  需求(不改 PnL/費用/sizing/成交/閘門的正式規則,只是加報表輸出)
- 在 feature branch 工作,不 commit 到 main

### ACCEPTANCE CRITERIA(binary)

- [ ] `holdings_log` 預設關閉時,既有回測輸出 byte 級不變(測試斷言)
- [ ] 每個 rebalance:long 與 short 權重和各 ≈ 0.5(±1e-6),單幣 ≤ 0.1
- [ ] holdings.json 含 `params_frozen_from` 與 `notional_base_usd`,金額由
      權重換算,無捏造成交
- [ ] 既有 `results/strategy_finding_20260726/f_funding_xs_dispersion_retry1/`
      內原檔案 zero diff
- [ ] `snapshot_strategies.py` 讀入後頁面 JSON 通過其禁用鍵檢查(跑一次即驗)
- [ ] diff 只含 PERMITTED FILES

REPORT: 變更檔案、測試輸出尾段、假設、任何 UNCONFIRMED 項目。
