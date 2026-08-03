---
status: current
type: report
owner: codex
created: 2026-08-02
last_reviewed: 2026-08-02
expires: none
superseded_by: null
---

# 免費資料、論文與策略回測研究報告（2026-08-02）

## Executive Summary

- **本輪沒有任何新策略通過完整統計閘門，也沒有任何策略可直接用於實盤、Demo 或自動晉級。** 凍結 runner 的終端結果是 `PASS=0 / FAIL=7 / ERROR=0`；它機械性地讓三個候選進入 Stage 3。執行後依 ADR-0013 稽核，這三個候選的 power breadth 沒有獨立性論證，治理有效結論是七個候選都應在 Stage 2 停止。所有產物都明示 `promotion_gate_passed:false`、`portable_validation_gate:false` 與 `live_trading_authorized:false`。
- **本輪沒有治理有效的「接近門檻」新策略。** H-041 與 H-045 的機械性 Stage-3 DSR/PSR 分別為 0.9279、0.9128，但保守 breadth=1 後，其 Stage-2 MDS 分別升至 0.6384、0.6187，高於 plausible Sharpe 0.5671、0.5425；因此 Stage-3 數字只能作診斷，不能作 near-pass 證據。專案既有、治理有效且最接近 Stage-2 power 的方向仍是 H-023（plausible 0.5961 對 MDS 0.7134，約差 16%）。
- **可直接歸因於本次資料探勘與候選回測準備的補全小計是 13,347 筆唯一觀測。** 最重要的新維度是 Wikipedia 注意力、BTC/ETH 活躍地址、USDT 美元參考價與 DGS10；另補近期 Binance OI、Fear & Greed、Deribit 波動率/資金費率及 Binance BTC/ETH funding。四個新研究資料集各有 2,401 筆、無空值、無負發布延遲、無 `suspect` 標記。這不是 2026-08-02 全專案所有並行工作寫入的總數。
- **目前專案中唯一曾正式通過 Stage 3 統計門檻的是既有 H-014 波動率制度期權策略，但仍只能作研究/影子觀察。** E-051 的 WF/CPCV 為 1.3049/1.1326、DSR/PSR 0.9845；延長視窗 E-052 的 WF 降至 0.8818、CPCV 1.0098、DSR 0.9746、PSR 0.9904。它仍缺少便攜驗證、至少八週 shadow 與其他上線閘門，因此不可稱為 live-ready。

## 研究邊界與協作架構

本工作依專案既有協作契約執行，而不是從聊天記憶改策略假設：

- `research/strategy_synthesis.md`、`docs/backtest_live_parity_plan.md` 與 `config/` 是策略與執行真相來源；本輪沒有修改 Claude 所有的 `research/`。
- `docs/HYPOTHESIS_LEDGER.md` 與 `docs/EXPERIMENT_REGISTRY.md` 管理假設、家族累積試驗數與 K-budget；結果可見前先凍結 H-040 至 H-046 與 E-077 至 E-083。
- `docs/DOMAIN_RULES.md`、`docs/INVARIANTS.md`、`docs/FAILURE_MODES.md` 與 Change Manifest 管理發布時間、funding、成本、trial count 與失敗模式。
- 本輪只有五個真正不同且有免費資料可執行的新論文機制，加上兩個既有資料阻塞假設的重大迭代，未達 ADR-0016 的 8 新 + 2 迭代完整 round 要求。因此固定標示為 `limited_probe`、`complete_round:false`，不能在看到結果後用參數變體補足名額。

## 資料補全：新增了過去較少關注的四個維度

### 1. 本任務可直接歸因的淨新增資料小計

| 維度 / 資料集 | 來源 | 淨新增唯一列 | 目前範圍或更新窗 | 研究用途 |
|---|---|---:|---|---|
| `wiki_pageviews_bitcoin_en` | Wikimedia Analytics API | 2,401 | 2020-01-01 至 2026-07-28，日頻，D+1 | 公眾注意力與價格趨勢交互作用 |
| `cm_btc_active_addresses` | Coin Metrics Community | 2,401 | 2020-01-01 至 2026-07-28，日頻，D+1 | BTC 網路採用成長 |
| `cm_eth_active_addresses` | Coin Metrics Community | 2,401 | 2020-01-01 至 2026-07-28，日頻，D+1 | ETH 網路採用成長 |
| `cm_usdt_price_usd` | Coin Metrics Community | 2,401 | 2020-01-01 至 2026-07-28，日頻，D+1 | USDT 脫鉤事件研究 |
| `dgs10` | FRED / Federal Reserve H.15 | 1,645 | 2020-01-02 至 2026-07-30，工作日，D+1 | DGS10-DGS2 殖利率曲線風險狀態 |
| `oi_binance_btc`、`oi_binance_eth` | Binance Futures | 1,000 | 各 500 小時，2026-07-12 18:00 至 2026-08-02 13:00 UTC | 近期衍生品持倉監測；免費端點只有短史 |
| `fear_greed_btc` | Alternative.me | 34 | 目前共 3,101 日，更新至 2026-08-02 | 情緒資料新鮮度補齊 |
| Deribit DVOL/HV/funding 八個資料集 | Deribit public API | 908 | 更新至 2026-08-02 | 波動率與資金費率近期補齊 |
| Binance BTC/ETH funding | Binance Futures | 156 | 各新增 78 個結算；目前各 7,203 筆，至 2026-07-28 16:00 UTC | 本輪 PnL 的實際 funding 成本 |
| **合計** |  | **13,347** |  |  |

`13,347` 是上表所列、可直接歸因於本任務補全 slice 的資料庫唯一鍵淨增加量，不是 API 回傳列數，也不是同日所有並行 workstream 的總新增。當日較早另有 CFTC/Cboe、跨場 IV 與 liquidation 等其他工作寫入，未混入本小計。Binance OI 初次分頁在邊界重複一個小時 bucket，舊 ingest 統計錯報各 501；實際資料庫各 500。這次在 adapter 與共享 store 兩層修正為同批次最後一筆勝出、每個 `(dataset_id, observed_at)` 只計一次，並新增回歸測試。

### 2. 資料品質檢查

四個新研究資料集均為 2,401 個唯一 UTC 日，且：

- `value_num` 空值為 0；
- `published_at` 缺值為 0；
- `published_at < observed_at` 為 0；
- `quality_status='suspect'` 為 0；
- 預註冊回測正式窗使用 `[2020-01-01, 2026-07-29)`，所以產物中的 2,400 或 2,397 可用日是 end-exclusive、發布延遲、特徵暖機與市場交集造成，不是少下載。

這些檢查代表「基本欄位與時序一致」，不代表經濟內容已完整驗證。資料庫的 `data_quality_events` 仍為 0；這是「目前沒有被寫入的品質事件」，不能解讀成全庫無缺口。尤其 Coin Metrics `PriceUSD` 是日頻參考價，H-042 在凍結的嚴重脫鉤條件下完全沒有事件，證明它不足以測試交易所內短暫 depeg，而不是證明 USDT 從未脫鉤。

### 3. 既有核心資料狀態與沒有硬補的缺口

| 資料 | 現況 | 本輪決定 |
|---|---|---|
| Binance BTC/ETH 1m canonical candles | 各 3,446,654 列，2020-01-01 至 2026-07-29 08:05 UTC | 足以支援本輪 H-040 至 H-046 |
| Binance BTC/ETH funding | 各 7,203 結算，2020-01-01 至 2026-07-28 16:00 UTC | 安全 checkpoint top-up 已完成 |
| OKX BTC/ETH exact-venue 1m | 各 3,396,960 列，止於 2026-06-16 23:59 UTC；各缺 60,480 列至本輪終點 | 本輪候選不讀 OKX；現有 checkpoint 無法安全前推，未執行約 1,212 次 request 的非 checkpoint fallback |
| OKX funding | 長期官方歷史仍不足；官方介面通常只提供近三個月 | 無法誠實解除 H-010 的歷史阻塞，未以 Binance funding 代替 |
| Deribit option-flow 歷史 tape | 既有 aggregate drift 與不完整 full-tape 問題 | H-031/H-035 不恢復，不把近期刷新誤稱為歷史修復 |

這裡刻意沒有為了「看起來資料更多」而補未被本輪候選使用、且缺乏安全 checkpoint 的 OKX 分鐘資料。需要重新做 cross-venue 研究時，再以明確任務執行 bounded fallback 與 exact-venue verifier。

### 4. 授權與發布時間限制

- Wikimedia Analytics API 的資料採 [CC0 1.0，且要求可識別 User-Agent](https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/documentation/access-policy.html)。這是本輪最乾淨的新增公開來源。
- Coin Metrics Community 可免 API key 使用，但官方文件將免費資料限定為 [非商業使用、Creative Commons 授權](https://docs.coinmetrics.io/api)。因此 H-041/H-042 只能作研究證據；商業或 live 使用前要重新確認授權。
- DGS10 是 FRED 的 [10 年期美國公債固定到期殖利率日頻序列](https://fred.stlouisfed.org/series/DGS10)。本輪使用 latest-vintage + D+1；它不是 ALFRED 即時 vintage，若研究結果接近晉級，還需要修訂資料敏感度檢查。
- CFTC 說明 COT 通常在[週五 15:30 ET 發布前一週二的資料](https://www.cftc.gov/MarketReports/CommitmentsofTraders/ReleaseSchedule/index.htm)，假日可能延後。本輪保留 reference date，但直到發布時間後才可用。

## 論文探勘：哪些機制真正可轉成可證偽訊號

### 1. 本輪實際執行的五個新論文方向

| 假設 | 論文基礎 | 論文支持的機制 | 本專案凍結的可交易轉譯 | 結果邊界 |
|---|---|---|---|---|
| H-040 Wikipedia 注意力 × 趨勢 | Kristoufek, [Scientific Reports 2013](https://www.nature.com/articles/srep03415) | 無條件 Wikipedia views → price 並不顯著；將注意力按價格高/低於 7 日趨勢拆分後，效果同號且顯著 | views log change > 0 時，BTC 高於 7 日均線做多、低於時做空；D+1 + t+1 | 精確轉譯為負 Sharpe，拒絕此規格；不能把論文的同期/動態關係直接當交易獲利 |
| H-041 網路採用 | Bhambhwani, Delikouras & Korniotis, [JIFMIM 2023](https://www.sciencedirect.com/science/article/pii/S1042443123000562) | 網路規模與算力可解釋價格/預期報酬 | BTC/ETH 7 日活躍地址成長的每週方向；免費 hashrate 不可用，未代理 | 成本後邊際為正，但 breadth=1 功效不足；方向可研究，未重現完整 security factor |
| H-042 穩定幣嚴重脫鉤後反轉 | Foley, Lee & Milunovich, [Accounting & Finance 2026](https://onlinelibrary.wiley.com/doi/10.1111/acfi.70201) | depeg 與主要加密資產報酬具有同期及前後日關聯；嚴重負 depeg 提供可檢驗的次日反轉方向 | USDT < 0.99 且 past-only 60 日 z <= -3 後，下一可執行日等權做多 BTC/ETH 一日 | 免費日頻參考價零事件，資料不具事件解析度；機制未被否證 |
| H-043 橫截面 salience | Cai & Zhao, [Journal of Banking & Finance 2024](https://livrepository.liverpool.ac.uk/id/eprint/3182764) | 投資人過度加權顯著 payoff，向上 salience 資產後續報酬較低、向下 salience 較高 | PIT universe、7 日、`theta=0.1`、`delta=0.7`，每週 long bottom / short top quintile | 資料與差異性過關，但精確規格 Sharpe -0.6065；拒絕，不做參數追逐 |
| H-044 CFTC 參與者制度 | Hung, Liu & Yang, [Journal of Empirical Finance 2021](https://www.sciencedirect.com/science/article/abs/pii/S0927539821000207) | 不同參與者的交易活動影響 CME/CBOE futures price discovery | leveraged-money net/OI 的四次發布變化映射 BTC/ETH 方向，週五發布後 t+1 | 論文不保證報酬符號；本輪 transfer hypothesis 為負，拒絕且不做事後反號 |

### 2. 兩個既有方向的重大資料/時序迭代

- **H-045 / F-MACRO-EVENT-DRIFT：** 修復 H-033 的 DGS2 使用方式。已知 FOMC 日期可在 T-1 交易，但會議當日的兩年期殖利率變動不能回填到更早的決策時間；本輪只在 `published_at` 後再 t+1 持有兩日。
- **H-046 / F-XASSET-MACRO-LEAD：** 將 H-036 未取得且實際未使用的 gold 需求改成官方 DGS10-DGS2 曲線，VIX、美元與曲線都只使用已發布值，calendar forward-fill 最長七日，60 日 z-score 分布再延遲一天。

這不是偷偷改寫 E-072/E-073；舊產物保持不變，H-045/H-046 以新實驗列和相同家族累積 trial 記錄。

### 3. 有研究價值但未納入本輪執行的方向

- **GitHub/技術缺陷衝擊：** 找到的 2025 SSRN 研究所報告次日效果約 -7 bps，已低於本輪完整進出 8 bps，還需要 PIT flaw classifier 與可審計事件資料，因此沒有用 NLP 代理或忽略成本硬跑。
- **第二個鏈上 security 候選：** 同一篇 network fundamentals 論文的 hashrate leg 在 Coin Metrics Community 不可免費取得。把 active addresses 與 hashrate 拆成兩個「新家族」會重複計數，所以去重。
- **H-038 residual mean reversion 最後一次重試：** 它會消耗 F-S5 的終端 K 2/2。使用者的廣泛研究要求不等同於批准永久關閉該家族，因此本輪未執行。
- **H-028 liquidation reversal、H-039 cross-venue option IV：** 都是有方向但資料需向前累積的候選。H-028 誠實的約 12 個月觀察窗最早約 2027-07；H-039 需至少 270 日、最早約 2027-05。

## 回測契約：如何避免看見結果後調整

正式回測前建立 SHA-256 收據，凍結規格、ledger、registry、runner 與 CLI；驗證收據成立且輸出目錄不存在後，才執行一次。執行後 ledger/registry 的結果追加會自然使 pre-run hash 不再匹配，從而阻止同一 receipt 被重跑。

所有候選共用：

- Binance source-scoped 1m candles 形成 UTC 日收盤；funding 按實際結算**加總**，不取平均；
- 外部資料在 `published_at` 前不可用；target 整體再延遲一日；
- `gross = Σ(executed_weight × close_return)`；`funding = -Σ(executed_weight × daily funding)`；
- turnover 每一方向收 4 bps（2 bps fee + 2 bps slippage），完整進出為 8 bps；
- Stage 2 必須同時通過 data availability、distinctness、cost-after-edge、statistical power；
- power breadth 必須在資料庫存取前明示，且只能計入有獨立性論證的 bets，不能由非零交易腿數推定；
- 新家族與 BTC、BTC/ETH、E-031、所有保留的 E-045 cell 絕對相關低於 0.70，且每個比較至少 365 共同日；undefined correlation fail closed；
- Stage 3 只有 Stage-2 全過者才能執行，使用 WF 365/90 與 CPCV N=6、k=2、embargo 2%、purge 1；單一凍結 cell 的 `n_trials=1`；
- 統計通過需 DSR >= 0.95、PSR >= 0.95、DSR <= PSR、nonzero activity 與 trial reconciliation 全部成立。

### 執行後治理稽核：三個 reported Stage-2 passes 均不成立

正式產物完成後，逐條對照 ADR-0013 發現 runner 把「非零交易腿數中位數」直接當作 statistical-power breadth；H-041/H-045/H-046 因 BTC 與 ETH 兩腿而被當成 breadth=2，但規格沒有在資料存取前提供兩腿獨立性的論證。這不是參數敏感度，而是 Stage-2 eligibility 的治理錯誤。保守且合規的 breadth=1 重算如下；只使用已保存的樣本數與報酬矩，沒有重跑或改動策略：

| 假設 | 產物 breadth | 產物 MDS | Plausible Sharpe | 合規 breadth=1 MDS | 稽核結論 |
|---|---:|---:|---:|---:|---|
| H-041 | 2 | 0.4518 | 0.5671 | 0.6384 | Stage-2 power FAIL |
| H-045 | 2 | 0.4411 | 0.5425 | 0.6187 | Stage-2 power FAIL |
| H-046 | 2 | 0.4540 | 0.4838 | 0.6425 | Stage-2 power FAIL |

因此三組已生成的 WF/CPCV/DSR/PSR 都是**診斷性、不可採納的 Stage-3 證據**。它們已被看過，family trial 仍各記 1，不能倒扣；同時預註冊 receipt 已因執行後 ledger/registry 追加而失效，不能為了修正分類重跑。共享根因已修正：`power_breadth` 現在是每個候選的必填明示欄位，且在 receipt/DB access 前拒絕非有限或非正值；本輪七個候選均明示為 1。原始產物保持不變，另以治理稽核文件記錄更正。

## 七個候選的終端結果

| 假設 | Stage 2 | Net Sharpe | Plausible / 產物 MDS / 合規 MDS | 診斷 WF | 診斷 CPCV | 診斷 DSR / PSR | 判定 |
|---|---|---:|---:|---:|---:|---:|---|
| H-040 Wikipedia attention × trend | FAIL | -0.1938 | -0.1060 / 0.6334 / 0.6334 | — | — | — | 資料與差異性過關，成本後邊際及功效失敗；精確規格 refuted |
| H-041 active-address adoption | **產物 PASS／稽核 FAIL** | 0.5674 | 0.5671 / 0.4518 / 0.6384 | 0.4479 | 0.5674 | 0.9279 / 0.9279 | breadth 未獨立論證；方向可研究，但不具 Stage-3 eligibility |
| H-042 severe USDT depeg reversal | FAIL | 0.0000 | 無法估計 | — | — | — | 2,400 usable days、0 severe events；data-inconclusive，不是機制 refutation |
| H-043 cross-sectional salience | FAIL | -0.6065 | -0.6065 / 0.3324 / 1.0579 | — | — | — | PIT universe 與差異性過關，但邊際明顯為負；精確規格 refuted |
| H-044 CFTC participant regime | FAIL | -0.0860 | -0.0860 / 0.4533 / 0.6414 | — | — | — | 發布時序與差異性過關，transfer sign 為負；精確規格 refuted |
| H-045 FOMC/yield publication-safe iteration | **產物 PASS／稽核 FAIL** | 0.5042 | 0.5425 / 0.4411 / 0.6187 | 0.3416 | 0.5042 | 0.9128 / 0.9128 | breadth 未獨立論證；51 usable events / 139 held days，方向可研究 |
| H-046 macro-state official-yield-curve iteration | **產物 PASS／稽核 FAIL** | 0.4752 | 0.4838 / 0.4540 / 0.6425 | 0.1696 | 0.4752 | 0.8882 / 0.8882 | breadth 未獨立論證；資料路徑可研究，精確規格不接近晉級 |

三個機械性 Stage-3 候選的 CPCV 都保留五條、每條 2,398 日的 path return。由於它們是單一固定訊號、沒有 fold 內參數 refit，各 path 的 Sharpe 相同；這不是五個獨立模型的重複成功。三者的 `n_trials=1`、`caller_declared`、reconciled 與 nonzero activity 在原始執行內一致，但因 Stage-2 eligibility 稽核失敗，整組 Stage-3 證據不可用於治理決策。

## 哪些策略「可以用」、哪些接近、哪些值得繼續

### 可用：只有研究/影子用途，沒有 live-ready 策略

1. **H-014 / F-VOL-REGIME-OPT 是專案目前唯一曾正式通過 Stage 3 統計門檻的策略。** E-051 與 E-052 都通過 DSR/PSR，但延長窗 WF 已由 1.3049 降至 0.8818，顯示時間穩定性仍需 shadow 證據。可用於繼續影子觀察與驗證流程，不可直接交易。
2. **本輪 H-040 至 H-046 沒有可用策略。** 治理有效口徑下全部在 Stage 2 停止；不能用機械性正 Sharpe 或不可採納的 Stage-3 診斷繞過 power gate。

### 接近門檻但沒有通過

**本輪新候選沒有治理有效的 near-threshold。** H-041/H-045 的 DSR 0.9279/0.9128 是最接近的機械性診斷，但它們在合規 breadth=1 下已先失敗，不能列為正式 near-pass。

1. **H-023 既有 taker-flow 方向：** 過去 Stage-2 plausible Sharpe 0.5961，低於 MDS 0.7134 約 16%，尚未進 Stage 3；它是目前治理有效且最接近 power gate 的既有候選，只有在取得更長 OOS 或更直接的機制資料時才值得重開。
2. **H-041 active-address adoption（僅診斷接近）：** 成本後正邊際與 2,385 held days 支持繼續做資料研究，但合規 MDS 0.6384 高於 plausible 0.5671。下一步應增加獨立資料或補 security/hashrate，而不是在相同樣本上調 growth window。
3. **H-045 publication-safe FOMC/yield（僅診斷接近）：** 方向為正但只有 51 events；合規 MDS 0.6187 高於 plausible 0.5425。最有價值的增量是更長、revision-aware 的事件史，不是調持有天數。

H-009 曾在 E-031 到 DSR/PSR 0.9346，但正式 retry E-063 退化到 DSR 0.8305、PSR 0.9166，已 shelved；不能只挑舊結果把它重新列為 near-pass。

### 值得繼續探究，但不是立即重試

- **鏈上基本面：** H-041 是最佳新研究方向，但先要解除 breadth=1 功效缺口。確認商業授權，增加歷史或另一個不重複的安全性來源，再預註冊一次家族 retry；任何新窗口/指標都必須累計 trial/K。
- **宏觀事件與狀態：** H-045/H-046 已證明 publication-safe 資料管線可用。H-045 適合增加事件數與 real-time vintage；H-046 需先回答「風險狀態是否真的增加 buy-and-hold 的 OOS 價值」，而不是直接改投票門檻。
- **穩定幣壓力：** H-042 應先做資料研究，取得 exchange-specific、分鐘級、多 stablecoin 的 PIT 價格與事件完整性，再決定是否重跑。免費日頻 reference price 不足以測短暫脫鉤。
- **向前累積的微結構/跨場方向：** 維持 H-028/H-039 collector 健康，等樣本到門檻再做一次結果盲的 Stage 2；不要用縮短窗口換取提早結論。

### 不建議沿原規格繼續

- H-040、H-043、H-044 的精確規格在資料與時序可用時仍產生負成本後邊際；除非新論文提出不同經濟機制或資料結構，否則不應只換參數或反號重跑。
- H-046 的資料方向值得保留，但合規 power 已失敗，且診斷 WF 只有 0.1696，不應稱為 near-pass。
- H-031/H-035 在 Deribit 歷史 tape 完整性與 aggregate drift 解決前，不應恢復。

## 後續執行方向（依優先級）

1. **P0 — 維持不上線。** 不修改 live/shadow/demo gate，不把本輪任何正 Sharpe 候選接到策略 config；H-014 也要完成既定 shadow、便攜驗證、成本/流動性與人工批准。
2. **P1 — 完成 H-014 至少八週 shadow 與 parity 證據。** 這是目前離可決策最近的路徑；監控訊號日新鮮度、missed-entry、可執行 spread、實際手續費與每週樣本數。
3. **P1 — 對 H-041 做「資料增量」而非「參數增量」。** 先以 breadth=1 做前瞻功效設計，再延長 active-address OOS、尋找授權相容的 hashrate/security 來源或獨立鏈上 fundamental；新 retry 前記錄 family trial/K。
4. **P1 — 擴充 H-045 的 revision-aware FOMC/yield 事件史。** 先以 breadth=1 設計所需事件數，再使用 ALFRED 或官方 release-vintage 增加 2020 年前事件並維持 published-at + t+1。若樣本增加後仍不足，停止此家族。
5. **P2 — 為 H-042 建立 event-data feasibility，而不是先回測。** 取得 Binance/OKX/Coinbase 等分鐘級 USDT/USDC price、跨場偏離與可交易 liquidity；先驗證能否捕捉已知事件與發布時間，再預註冊策略。
6. **P2 — 強化資料品質可觀測性。** 將缺口、重複 boundary、stale、負發布延遲與 source drift 寫入 `data_quality_events`；目前 count=0 不是完整品質證明。
7. **P3 — 只有 cross-venue 工作獲准時才補 OKX 1m/funding。** 執行 bounded fallback 後必須用 exact-venue verifier；不可由 resolved canonical coverage 推斷 OKX 完整。

## 仍需回答的問題

- Coin Metrics Community 的非商業條款是否符合預計的研究/產品使用方式？若不符合，H-041/H-042 即使統計改善也不能進 deployment gate。
- H-041 的診斷 DSR 0.9279 是否由 2020–2021 adoption regime 驅動？只有在先取得 breadth=1 Stage-2 eligibility 後，才值得做不新增參數的 pre/post regime 穩定性診斷。
- H-045 加入更長 real-time vintage 後，正邊際來自 pre-FOMC calendar leg 還是 lagged yield leg？下一個假設必須先註冊 attribution，不可事後挑 leg。
- H-014 的 shadow 結果是否能在真實 chain、quote staleness、fill probability 與費用下重現研究上限？

## 重要限制與風險

- 本輪是七候選 limited probe，不是 ADR-0016 完整自動找策略 round；沒有用不足十個候選假裝完成 quota。
- runner 原本違反 ADR-0013，把 active legs 當 power breadth；治理稽核已將三個 reported Stage-2 passes 更正為 FAIL。修正版程式不重跑本輪 frozen experiment，原始 artifact 只作可追溯診斷。
- 回測是日頻固定訊號研究，不代表 intraday fill、queue、latency、contract multiplier 與 live risk gates 已驗證。
- H-042 的零事件是 source-resolution failure；H-040/H-043/H-044 才是規格在可用資料下的負證據。
- FRED 使用 latest vintage；宏觀資料修訂風險尚未以 ALFRED 重建。
- Coin Metrics 的免費資料授權是 research/noncommercial；資料可下載不等於可商業再散布或 live 使用。
- 正式 aggregate `limited_probe_report.json` 本身有獨立 SHA-256 `66a37603b2da3a5f658a9c781ea8b4882ee07c3f1dad5af0a624f319acf70d39`，但 runner 的候選 `sha256.json` 只覆蓋每個 candidate artifacts，不包含 aggregate；報告引用時兩者都已另行重算核對。
- `terminal.json` 沒有獨立欄位明示 consumed trials；依 stop rule，H-040/H-042/H-043/H-044 消耗 0，H-041/H-045/H-046 各執行一個凍結 cell。Registry 已明確記錄，避免把 Stage-2 power 中的 prospective `n_trials=1` 誤讀成已消耗。

## 主要證據與外部來源

- 預註冊規格：`docs/superpowers/specs/2026-08-02-paper-data-limited-probe.md`
- 預註冊收據：`tasks/2026-08-02-paper-data-limited-probe-preregistration-receipt.md`
- 執行後治理稽核：`tasks/2026-08-02-paper-data-limited-probe-governance-audit.md`
- 終端 aggregate：`results/paper_data_limited_probe_20260802/limited_probe_report.json`
- 每候選 Stage-2/Stage-3/PnL/weights/hash：`results/paper_data_limited_probe_20260802/`
- 策略歷史與分類：`docs/HYPOTHESIS_LEDGER.md`、`docs/EXPERIMENT_REGISTRY.md`、`docs/STRATEGY_HISTORY.md`
- 公開資料政策：[Wikimedia Analytics API](https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/documentation/access-policy.html)、[Coin Metrics Community API](https://docs.coinmetrics.io/api)、[CFTC COT release schedule](https://www.cftc.gov/MarketReports/CommitmentsofTraders/ReleaseSchedule/index.htm)、[FRED DGS10](https://fred.stlouisfed.org/series/DGS10)
