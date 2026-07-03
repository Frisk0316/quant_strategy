---
status: current
type: reference
owner: claude
created: 2026-07-03
last_reviewed: 2026-07-03
expires: none
superseded_by: null
---

# 統計功效 × 現行閘門（DSR/PSR ≥ 0.95）規劃參考

> **本文件不改任何閘門。** 閘門變更需使用者明確批准 + ADR
> （`docs/ai_collaboration.md`）。這是一份「在現有資料長度下，什麼樣的
> Sharpe 才推得過閘」的量化規劃指引，用來排資源優先序，
> 對應 2026-07-03 使用者決策 3。

## 1. 問題

到 2026-07 為止 7 個 family 全數 refuted/shelved/inconclusive。閘門正確地拒絕
了它們——但沒人寫下一個結構事實：**以 ~2.5 年歷史（2024-01 → 2026-06）配
DSR/PSR ≥ 0.95，對 multi-day 策略而言，能過閘的真實 Sharpe 門檻高得驚人。**
不把這個量化，資源會繼續花在統計上幾乎不可能過閘的搜索上。

## 2. 假設與方法（近似，供規劃用）

- 報酬近似 iid、常態；日頻觀測、365 天年化（crypto 全年交易）。
- Sharpe 估計標準誤（年化）：`σ_SR ≈ sqrt(1/T_years)`
  （精確式 `sqrt((1+SR²/2)/n)·sqrt(365)`；SR 不大時差異次階）。
- 多重檢定基準（Bailey & López de Prado DSR）：N 個 trial 下，零效應的期望
  最大 Sharpe `E[maxSR₀] ≈ c(N)·σ_SR`，
  `c(N) = (1−γ)·Φ⁻¹(1−1/N) + γ·Φ⁻¹(1−1/(N·e))`，γ≈0.5772。
- `DSR ≥ 0.95` 需要觀測 SR ≥ `E[maxSR₀] + 1.645·σ_SR`。
- 「80% 檢定力」= 真實 SR 需再高 `0.84·σ_SR`，觀測值才有 80% 機率過線。
- 忽略偏態/峰度修正（實作中的 DSR 有含；此處為規劃級近似）。實際單一 run 的
  判定一律以實作 DSR + retained `path_returns` 為準，不用本表。

## 3. 主表：T = 2.5 年（σ_SR ≈ 0.63）

| family 累計 n_trials (N) | c(N) | 過 DSR≥0.95 所需**觀測**年化 Sharpe | 80% 檢定力所需**真實** Sharpe |
|---:|---:|---:|---:|
| 1（僅 PSR） | 0 | ≈ 1.0 | ≈ 1.6 |
| 4 | 1.05 | ≈ 1.7 | ≈ 2.2 |
| 9 | 1.52 | ≈ 2.0 | ≈ 2.5 |
| 24 | 1.98 | ≈ 2.3 | ≈ 2.8 |
| 48 | 2.26 | ≈ 2.5 | ≈ 3.0 |

對照歷史：C2 idealized 假象給過 6.9（假 vol）；其餘全部落在 0.5–1.2 的觀測
Sharpe——距離 N=24 的 2.3 門檻不是「差一點」，是**差一個數量級的樣本量**。

## 4. 歷史長度敏感度（N = 24）

| 歷史長度 T | σ_SR | 所需觀測 Sharpe | 80% 檢定力真實 Sharpe |
|---:|---:|---:|---:|
| 2.5 年（現況） | 0.63 | ≈ 2.3 | ≈ 2.8 |
| 5 年 | 0.45 | ≈ 1.6 | ≈ 2.0 |
| 10 年 | 0.32 | ≈ 1.15 | ≈ 1.4 |

**取樣頻率救不了功效**：年化 Sharpe 估計精度一階只依賴總年數 T，不依賴日內
取樣密度。能救的只有 (a) 更長的歷史、(b) 結構上更高的真實 Sharpe。

## 5. 規劃含意（不改閘門的前提下）

1. **小網格是一階槓桿。** N=4 vs N=48 的過閘門檻差 ~0.8 年化 Sharpe。
   pre-registered grid 越小越好；「多掃幾組參數」在現行歷史長度下是自毀行為。
2. **retry 極貴。** 每次 retry 疊 n_trials、抬 c(N)。對 refuted family，
   「shelve 等新資料/新機制」通常是統計上正確的選擇——這正是 K_limit=2 的
   統計學理由。
3. **對 refuted 結果的正確解讀**：在 2.5 年樣本上，「refuted」多半意味著
   「真實 edge（若有）小到與零不可分」，而非「證明為零」。因此**不要**
   對同 family 換皮重試（只會燒 N）；要嘛等資料變長，要嘛換結構上
   Sharpe 更高的機制。
4. **搜索空間應向「結構性高 Sharpe」的 family 傾斜**：微結構/日內/事件驅動
   （taxonomy 的 F-OFI-MAKER-SKEW、F-VPIN-MM、F-LIQUIDATION-CASCADE、
   F-XVENUE-LEADLAG）的可信真實 Sharpe 天花板遠高於擁擠的 multi-day 效應
   ——而它們恰好全在資料封鎖區。**這是把資源優先給資料解鎖任務
   （P1/P5/P8，見 `tasks/2026-07-03-pipeline-improvement-tasks.md`）的
   統計學論證。**
5. **歷史每多一年都有實質回報**（表 §4）：資料回補（更早的歷史，如
   Binance Vision 2021 起的 OI/1m 資料）與時間推移同等重要。

## 6. scope / role

Claude 撰寫（docs-only，2026-07-03 使用者批准）。不改
`docs/ai_collaboration.md` 閘門、不改 DSR/PSR 實作與門檻、不構成任何
promotion 證據。單一 run 的裁決仍以實作 DSR/PSR + checkpoint① 為準。

Related: [[HYPOTHESIS_LEDGER]] · [[EXPERIMENT_REGISTRY]] ·
[2026-06-30-stage3-idea-ingestion-design.md](2026-06-30-stage3-idea-ingestion-design.md) ·
[2026-06-30-mechanism-taxonomy.md](2026-06-30-mechanism-taxonomy.md)
