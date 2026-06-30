---
status: draft
type: design
owner: human
created: 2026-06-30
last_reviewed: 2026-06-30
expires: none
superseded_by: null
---

# Drafted 候選 → Stage-3 可執行契約

> 解開 [idea-generator-frontend-design.md](2026-06-30-idea-generator-frontend-design.md)
> 一條龍 driver(任務 ①)的前置。發想器現在只產到「`pending_llm` / `drafted`(hypothesis
> 文字 + `planned_grid_size`)」;但 Stage-3 回測在 `scripts/run_pipeline_batch2_checkpoint.py`
> 是**硬編** grid / 資料載入 / 驗證 / signal 函式的。本契約定義「一張草稿要帶哪些**結構化**
> 欄位,driver 才跑得動」,並把「generator/LLM 可宣告」與「Codex 必實作」切清楚。
> `status: draft`,等複審。不改任何 deployment/demo/shadow/live gate。

## 1. 現況 gap(為何需要這份契約)

`run_c1/c2/c3` 每個都長一樣的形狀,但全寫死:

```text
grid = {param: [values...]}                       # 參數網格 → grid_size
close/funding = load_cX_inputs(symbols, start, end, exchange)   # 資料
records = <vectorized signal fn>(inputs, grid)    # ← 每個 family 自己的 signal 函式
n_trials = len(records)                            # 本次 grid 數
validation = _refit_validation(records, n_trials) # WF/CPCV fold-refit
summary = _base_summary(dir, family, n_trials, validation, leak_test_passed, swap_symbols)
+ Stage-2 FeasibilityCheck(...) inline
```

driver 要通用,就不能再 `if candidate == c1 ...`;它要能從**一張結構化候選**讀出上面每一格。

## 2. 兩類欄位:宣告 vs 實作（關鍵切分）

- **generator / LLM 可宣告(資料、不需寫碼)**:grid、資料 spec、驗證參數、成本模型、
  family、n_trials、leak 測試指標 —— 這些是**參數**,LLM 草擬時就能填。
- **Codex 必實作(碼)**:`signal_fn` —— 把資料 + 一組參數算成部位/報酬序列的**向量化函式**。
  - **既有機制(retry/變體)**:函式已存在(C1/C2/C3、xs_momentum 等),只填 registry key。
  - **真新機制(frontier,如 F-FUNDING-XS-DISPERSION)**:需 Codex **實作一支新 signal fn**
    (一次),註冊進 registry,之後 driver 就能對它跑任意 grid。**這步無法用宣告繞過——
    算一個新訊號本來就要寫碼。**

→ 所以「全自動」對既有 family 成立;對真新 family,中間插一個**一次性 Codex signal 實作**,
之後該 family 全自動。這是誠實邊界,不是缺陷。

## 3. 可執行候選 schema（machine-readable）

driver 消費的單位。`executable: true` 才進 Stage-3;否則停在 `drafted` 等 signal 實作。

```jsonc
{
  "candidate_id": "B-f-funding-xs-dispersion",
  "hypothesis_id": "H-0xx",            // 來自 ledger 草稿
  "family_id": "F-FUNDING-XS-DISPERSION",
  "candidate_dir": "funding_xs_dispersion",

  "signal_ref": "funding_xs_dispersion",   // ← strategy registry key (§4);無對應實作 → executable:false
  "executable": true,

  "data": {                            // 對齊 load_cX_inputs(...)
    "exchange": "binance",
    "symbols": ["BTC-USDT-SWAP", "ETH-USDT-SWAP", "..."],  // universe
    "bar": "1m",
    "start": "2024-01-01", "end": "2026-06-16T23:59:00Z",
    "required_series": ["candles", "funding"],            // candles|funding|external
    "min_coverage": 0.80
  },

  "grid": {                            // param → 值列表;組合數 = grid_size_this_run
    "lookback_days": [7, 14, 30],
    "long_quantile": [0.2, 0.3],
    "rebalance": ["daily", "weekly"]
  },

  "validation": {                      // 預設 = 既有 fold-refit harness
    "wf": {"train_days": 365, "test_days": 90},
    "cpcv": {"N": 6, "k": 2, "embargo_pct": 0.02, "purge": 1}
  },

  "cost_model": {                      // 沿用 C2 realism 的旋鈕
    "fee_bps": 2.0, "slippage_bps": 3.0,
    "basis_execution_slippage_bps": 0.0, "carry_cost_bps": 0.0
  },

  "family_cumulative_n_trials": 0,     // 從 ledger 讀 family 累計(I23/I26);本批 grid 會疊加
  "leak_test": "tests/unit/test_funding_xs_dispersion.py::test_no_lookahead",  // 必填,須存在且綠

  "draft_status": "executable",
  "feedback_spawned": false
}
```

**最小必填(executable:true 的條件)**:`candidate_id`、`family_id`、`signal_ref`(已註冊)、
`data`(齊全)、`grid`(非空)、`validation`、`leak_test`(存在)、`family_cumulative_n_trials`
(來自 ledger,不寫死)。缺任一 → `executable:false`,driver skip 並記原因。

## 4. strategy registry（讓 driver 通用,取代硬編 run_cX）

新增一個 `family/signal_ref → vectorized signal fn` 註冊表(Codex 區,`backtesting/`):

```python
# backtesting/pipeline_strategy_registry.py
SIGNAL_FNS = {
  "c1_pairs_ou": run_c1_signal,
  "c2_funding_carry": run_c2_signal,
  "c3_sentiment": run_c3_signal,
  "xs_momentum": scan_xs_momentum,
  # frontier(待 Codex 實作):
  # "funding_xs_dispersion": run_funding_xs_dispersion_signal,
}
```

- signal fn 簽章統一:`fn(inputs, params) -> records`(records 餵 `_refit_validation`)。
- driver 用 `signal_ref` 查表;查不到 → `executable:false`(→ 觸發「需 Codex 實作此 family」)。
- **把現有 run_c1/c2/c3 的 signal 計算抽成註冊函式**是這條的主要重構(行為不變)。

## 5. draft_status 生命週期

```text
pending_llm  → (研究 subagent 草擬 hypothesis + 填 grid/data/validation) → drafted
drafted      → (signal_ref 已註冊?) ── 是 → executable
                                      └─ 否 → 卡住:開「Codex 實作 signal fn」子任務 → 註冊 → executable
executable   → driver 跑 Stage-2 → Stage-3 → checkpoint①
```

## 6. driver（任務 ①）如何消費本契約

driver 對每個 `executable` 候選,純串既有元件、不重造:
1. **Stage-2**:用 `data` 探 `pipeline_feasibility` 的 data_availability + distinctness(§7
   family-minting)+ cost_after_edge → 寫 `stage2_feasibility.json`;FAIL → skip。
2. **Stage-3**:`load_*(data)` → `SIGNAL_FNS[signal_ref](inputs, grid)` → `records` →
   `_refit_validation(records, family_cumulative + grid_size)` → `_base_summary(...)` →
   `checkpoint1_auto.json`(既有 checker)。
3. 彙整通過者進短名單;全部不碰 deployment gate。

→ driver 因此是**薄編排**(reuse `load_*` / `SIGNAL_FNS` / `_refit_validation` / `_base_summary`
/ `pipeline_feasibility` / `pipeline_checkpoint1`),不是新框架。符合原設計「driver = subagent
管線,不是 framework」。

## 7. 對 frontier 的意涵（接著要跑的首批次）

`F-FUNDING-XS-DISPERSION` 是 frontier、資料可行,但**沒有現成 signal fn**。所以首批次的路徑是:
1. 發想器列它為 eligible(已驗)。
2. 我/研究 subagent 把它草擬成 `drafted`(填本契約的 grid/data/validation)。
3. **Codex 實作 `run_funding_xs_dispersion_signal` + leak 測試 + 註冊**(一次性,本契約 §4)。
4. driver(①)跑它 → Stage-2 → Stage-3 → checkpoint①。

→ 也就是說,**首批次(任務 2)正好會逼出並驗證本契約**:跑的過程會發現契約缺欄位就補。

## 8. 重用 vs 新增 / scope

**重用**:`load_cX_inputs`、`_refit_validation`、`_base_summary`、`pipeline_feasibility`、
`pipeline_checkpoint1`、`pipeline_family_minting`、ledger n_trials/K。
**新增(最小)**:(a) 本可執行候選 schema(generator/adapter 多輸出這幾個結構化欄位);
(b) `pipeline_strategy_registry.py`(把 run_cX signal 抽成註冊函式);(c) 每個真新 frontier
family 一支 signal fn + leak 測試(Codex,逐案)。
`// ponytail: 契約 = 把 run_cX 已硬編的東西變成資料 + 一張 registry;driver 只是查表串接`

- 本檔為設計/治理文件,Claude 可寫。registry、signal fn、driver 屬 Codex(`backtesting/`、
  `scripts/`);LLM 草擬屬研究 subagent。發布權仍在使用者,不改任何 gate。
