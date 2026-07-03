---
status: draft
type: design
owner: human
created: 2026-06-30
last_reviewed: 2026-06-30
expires: none
superseded_by: null
---

# 機制 taxonomy 初始清單（Stage-3 ingestion 發想空間）

> 對應 [stage3-idea-ingestion-design.md](2026-06-30-stage3-idea-ingestion-design.md)
> 決策 2(發想來源 = 文獻 + **機制 taxonomy**)。這份是「自動發想器可以鑄 family 的經濟
> 機制地圖」+ family-minting 規則。`status: draft`,等使用者複審。
>
> **真相來源關係(別搞混)**:
> - [HYPOTHESIS_LEDGER.md](../../HYPOTHESIS_LEDGER.md) = family 的**裁決 + n_trials 真相**(權威)。
> - [research/strategy_synthesis.md](../../../research/strategy_synthesis.md) = 策略**假設**真相(權威)。
> - **本檔 = 機制空間的地圖 + 鑄 family 規則**,不覆寫上兩者;鑄出的新 family 一律回寫 ledger。

## 1. 為什麼需要這張地圖

自動發想最大的作弊面是「鑄無限新 family 把 K 歸零、稀釋 deflation」(見 ingestion §4.2)。
要擋它,得先有一張**已知機制空間**:任何自動產生的想法先比對這張表——能歸到既有 family 就
**繼承其 n_trials 額度 + K + 裁決**;只有真的落在表外的新機制才准鑄新 family。這張表就是
family-minting 的裁決基準。

## 2. 機制 taxonomy 初始清單

status:`occupied`=已在 ledger(帶裁決);`untested`=research 已記載但未成 family;
`frontier`=本檔新提、未經 research 審查。資料可得性對齊本 repo 現況(Binance/OKX perp+spot
1m candles + 8H funding 在 canonical DB;部分 L1 book replay;**無** options/IV、OI 史、
liquidation feed、on-chain)。

> **2026-07-01 使用者決策(資料蒐集政策,已修正)**:
> 1. 只要能不靠 API key、直接用公開 REST request 下載,就下載——不因為「多一道蒐集工程」
>    自我設限。
> 2. 跨所比對是**允許且鼓勵**的;OKX、Bybit 的 keyless 連接器已經在
>    `scripts/market_data/ingest.py`(`OKXPublicClient` / `BybitPublicClient`,
>    `--exchange okx|bybit`,checkpointed/resumable,寫入 `canonical_candles` /
>    `funding_rates`)裡接好,不需要新寫程式碼,只需要實際跑。
> 3. 因此 F-XVENUE-LEADLAG**不 deprioritize**;OKX BTC/ETH-USDT-SWAP 1m 回補已於
>    2026-07-01 用既有 ingest 工具啟動(見下方 family 列的即時狀態)。

| Family ID | 機制 | 經濟理由(為何淨成本後該有 edge) | 資料 | status / 裁決 | distinctness 鄰居 | crowding/decay |
|---|---|---|---|---|---|---|
| F-FUNDING-CARRY | delta-neutral 現/永續 funding carry + basis 濾網 | 收 funding 溢酬,對沖方向風險 | available | occupied / **refuted-shelved**(H-007) | F-S7-BASIS, F-FUNDING-XS | 高(眾所周知) |
| F-S7-BASIS-MEANREV | perp-vs-spot basis z 均值回歸 | basis 收斂 | available | occupied / **shelved**(H-003) | F-FUNDING-CARRY, F-PAIRS-OU | 中 |
| F-PAIRS-OU | BTC/ETH RV,OU 半衰期閘 | 配對共整合回歸 | available | occupied / **refuted**(H-006) | F-S5, F-S7 | 中 |
| F-S5-RESIDUAL-MEANREV | 殘差籃子均值回歸(剝離 BTC/ETH beta) | 特異性回歸 | available(universe) | occupied / **inconclusive**(H-004,資料-universe) | F-PAIRS-OU, F-XS-MOMENTUM | 中 |
| F-S6-TS-MOMENTUM | BTC/ETH 時序動能,vol-target | 趨勢持續 | available | occupied / **inconclusive**(H-005) | F-XS-MOMENTUM, F-VOL-REGIME | 高(擁擠) |
| F-XS-MOMENTUM | dollar-neutral 橫斷動能 top-30 | 橫斷報酬延續 | available | occupied / **refuted-shelved**(H-002) | F-S6, F-S5 | 高 |
| F-SENTIMENT | Fear&Greed long/flat | 情緒過度反應 | available(F&G 已 ingested) | occupied / **refuted**(H-008) | F-ONCHAIN-FLOW | 高 decay |
| F-OFI-MAKER-SKEW | 多層 order-flow-imbalance 掛單偏斜(S1) | 規避逆選擇、賺 queue 價值 | **partial/blocked**(需 L2 book + maker fills) | untested-documented | F-VPIN-MM | 中 |
| F-VPIN-MM | VPIN 毒性節流做市(S2) | 依 flow 毒性擇時做市 | **partial/blocked**(需 trade tape/VPIN) | untested-documented | F-OFI-MAKER-SKEW | 中 |
| F-VOL-REGIME | 波動體制濾網(S8) | 條件化 sizing/擇時 | available | untested-documented(**overlay,非獨立 alpha**——必須掛在某 base family 上,共用其額度) | (全部) | 低(meta) |
| F-CME-GAP | CME BTC 週末跳空(S10) | 日曆微結構失效 | **blocked**(需 CME 日線;舊 artifact 已刪) | untested-documented(research baseline,資料受限) | (calendar) | 中 |
| F-FUNDING-XS-DISPERSION | 橫斷 funding 排序(做多低/做空高 funding 永續) | funding 當全 universe 的擁擠/持倉溢酬 | **available**(E-030 data_availability PASS;E-031 Stage-3 checkpoint① 2026-07-03/04 已跑:MINT 過 distinctness[corr 0.138 vs F-FUNDING-CARRY],WF 1.18/CPCV 0.96/DSR=PSR 0.9346 差 0.95 邊緣未達,**使用者裁決 KEEP testing 不 refute**,K 0/2,禁 chase-the-gate 重試) | **occupied / testing**(H-009,n_trials=4) | ✓ 已量化區辨:corr 0.138 + Stage-1 機制論證(`2026-07-04-f-funding-xs-dispersion-hypothesis.md`);MINT 成立 | 高 |
| F-XVENUE-LEADLAG | 跨所價格領先落後(Binance↔OKX) | 資訊傳遞延遲 | **backfilling**(OKX BTC/ETH-USDT-SWAP 1m 2026-07-01 前為 0 列;已用既有 keyless `scripts/market_data/ingest.py --exchange okx` 啟動回補,完成後重跑 `run_pipeline_stage2_data_probe.py` 重新判定) | frontier-unvetted | F-XS-MOMENTUM | 中(容量受限) |
| F-OI-POSITIONING | 未平倉量 × 價格背離 | 持倉解單 / 逼倉 | **available**(BTC/ETH:2026-07-03 Binance Vision 5m OI 史已 ingest,`oi_binance_hist_{btc,eth}` 各 262,814 列 2024-01-01→今,0 缺日;其他標的可用同來源擴充) | frontier-unvetted | F-FUNDING-XS-DISPERSION | 中 |
| F-LIQUIDATION-CASCADE | 順/逆清算驅動的位移 | 強制流動性回歸 | **partial**(前向累積 2026-07-03 起:OKX liquidation-orders REST keyless,`liq_okx_{btc,eth}`;⚠ 保留窗僅數小時[BTC≈14h/ETH≈5h @1600列],不排程每2-4h ingest 就漏事件;無歷史深度) | frontier-unvetted | F-OI-POSITIONING | 高 |
| F-ONCHAIN-FLOW | 交易所淨流 / 穩定幣供給 | 鏈上持倉訊號 | **blocked**(無 on-chain) | frontier-unvetted | F-SENTIMENT | 高 decay |
| F-VOL-RISK-PREMIUM | 系統性賣波(realized < implied) | 變異數風險溢酬 | **blocked**(無 options/IV) | frontier-unvetted | F-VOL-REGIME | 中 |

## 3. family-minting 決策程序(自動發想器的硬規則)

對每個自動產生的想法,依序:

1. **機制比對**:它的經濟機制能否歸到表中某既有 family?
   - 能,且該 family `occupied`(已有裁決)→ **繼承該 family 的 n_trials 額度 + K + 裁決**。
     若該 family 是 `refuted`/`shelved` 且這個想法**沒有帶新機制轉折** → **直接 skip,不重燒
     compute**(查 ledger:H-002/H-006/H-007/H-008 已 refuted)。
   - 能,且該 family `untested`/`frontier` → 用該 family id,走 Stage 1→2,不另鑄。
2. **distinctness 量化 backstop**(重用 ingestion §4.2 + RD-Agent IC 去重):候選 signal 與
   **所有 enabled + 表中 occupied** family 的代表 signal 算相關/IC;超過門檻 → 視為最近的
   family(繼承),**不鑄新**。擋掉「換皮繞 K」。
3. **唯有**真的落在表外的新經濟機制 + 通過 distinctness → **鑄新 F-XXX**:寫 prior(機制敘述 +
   ex-ante 淨成本後 edge 理由)、K 歸零、**append 進本檔 + 回寫 HYPOTHESIS_LEDGER**。此鑄造
   決定落帳供 checkpoint① #9 / per-batch 稽核人審。

> ⚠ 特別注意 **F-FUNDING-XS-DISPERSION vs F-FUNDING-CARRY**:兩者都用 funding,極易被當成
> 換皮。橫斷 dispersion(跨標的排序)與單名 delta-neutral carry 是**不同機制**才可分家;若
> 實作出來的 signal 與 F-FUNDING-CARRY 高度相關,歸 F-FUNDING-CARRY(吃其 48 trials + 已
> refuted),不另鑄。

## 4. 給自動發想器的取捨指引(誠實版)

- **既有 occupied family 多數已 refuted/shelved/inconclusive**(2024–26 BTC/ETH perp 上,
  價格動能/均值回歸/carry/sentiment 的淨成本後 edge 都弱)。重試這些 = 墊高自己門檻,除非帶
  真的新機制轉折,否則別碰。這本身是研究訊號,不是 bug。
- **資料上目前真正可行的 frontier**:`F-FUNDING-XS-DISPERSION`(Binance funding 齊,但
  universe 資格認定另有 bug,見 `docs/AI_HANDOFF.md` 2026-07-01 記錄)、`F-XVENUE-LEADLAG`
  (OKX BTC/ETH-USDT-SWAP 1m 2026-07-01 已啟動回補,見上表),以及掛在 base family 上的
  `F-VOL-REGIME` overlay。發想優先往這幾格。
- **資料蒐集不自我設限於單一交易所**:只要有 keyless 公開 REST 可以下載(OKX、Bybit 皆已
  透過 `scripts/market_data/ingest.py` 接好連接器),需要跨所比較的 family 就正常排入
  優先序,不因為「要多蒐集一個交易所」而預先剔除。
- **目前 data-blocked(Stage 2 會直接 skip)**:OI、liquidation、on-chain、options/IV、
  完整 L2/trade tape——這些是**因為沒有 keyless 公開歷史 API**(或如清算只有即時 WS、
  無法回填 2024 起的窗口)才 blocked,不是交易所選擇問題。要解鎖得先做資料 ingestion
  (屬另一條工作流,非本管線)。
- 這份「哪裡還有先驗」正是 ingestion §2 那句「真槓桿是先驗品質」的操作化:把 compute 導向
  feasible + 高先驗格,而不是把已 refuted 的格再掃一遍。

## 5. 維護

- **append-only + 版本化**:自動 run 鑄出的新 family 追加到 §2 表尾(不刪舊列);裁決永遠以
  HYPOTHESIS_LEDGER 為準,本檔只記「機制 + 資料 + distinctness 鄰居 + 當前 status 指標」。
- 與 research/strategy_synthesis.md 衝突時以後者為策略假設真相;本檔若提出 research 未載的
  frontier family,鑄造前須補一段 Stage-1 spec(等同把 frontier 條目升級為 documented)。
- `// ponytail: 一張 markdown 表 + 既有 ledger,不建 DB、不建 factor store`

## 6. scope / role

- 本檔為設計/研究治理文件,Claude 可寫。它**不啟用任何策略、不碰 deployment/demo/shadow/live
  gate**;frontier family 在通過 Stage 1→3 + 全 gate 前都只是「可發想的格子」,不是 edge 證據。
- 鑄 family 的實際程式判定(distinctness 計算、ledger 回寫)屬 Codex 實作,接 ingestion 前段時做。

## 7. Codex 任務(family-minting distinctness checker)

實作 §3 決策程序的機器可判定部分。它是**純決策函式**(像 `pipeline_checkpoint1.py`):
餵入候選 signal + 一組參照 signal + ledger,輸出「ASSIGN / MINT / NEEDS_HUMAN /
SKIP_RECOMMENDED」決定。**參照 signal 從哪來由呼叫端(ingestion driver)供給,不在本件
範圍**——這樣它能獨立測試,不必等發想前段。這把決策 4(跨輪回饋)的 K-規避安全鎖補上。

```text
Task: 實作 family-minting distinctness checker,把 §3 的量化 backstop 自動化
Strategy/spec source: 本檔 §3 + stage3-idea-ingestion-design §4.2 + HYPOTHESIS_LEDGER
Required behavior:
  - 新增 backtesting/pipeline_family_minting.py(純函式):
    decide_family_minting(candidate_signal, reference_signals: {family_id: series},
                          claimed_family_id_or_NEW, claimed_mechanism, ledger_path) -> dict
    流程:
      (1) 算 candidate 與每個參照 signal 的 |相關|(對齊時間軸,pairwise complete);取 max。
      (2) 讀 ledger 取各 family 的 status + family_cumulative_n_trials —— **重用
          pipeline_checkpoint1.py 既有的 EXPERIMENT_REGISTRY/family 解析**;若還不是可重用
          函式,做最小 refactor 抽出共用,不改其行為。
      (3) 決策:
          - max_abs_corr >= HARD_ASSIGN_CORR(預設 0.90)→ ASSIGN 到最近 family,**不得 MINT**;
            若最近 family 是 refuted/shelved 且未宣告新機制轉折 → SKIP_RECOMMENDED。
          - HARD_ASSIGN_CORR > max_abs_corr >= BORDERLINE_CORR(預設 0.70)→ NEEDS_HUMAN
            (是換皮還是真新機制 = checkpoint① #9 人審)。
          - 宣告 NEW 且 < BORDERLINE_CORR → MINT 資格(但 human_review_items 必含
            mechanism_novelty;真正新穎由人確認,K=0 為 provisional)。
          - 宣告既有 family_id → ASSIGN(繼承其 n_trials + K),不 MINT。
      (4) ASSIGN 時回填 inherited n_trials + K;MINT 時 K=0 並標 provisional_new_family。
  - 新增 scripts/run_pipeline_family_minting_check.py(CLI):吃 candidate + refs + ledger,
    寫 family_minting.json(schema 見下),human_review_items 永遠非空。
  - 在 docs/INVARIANTS.md 新增 I27。

family_minting.json schema:
  schema_version, batch_id, candidate_id, claimed_family_id_or_NEW, claimed_mechanism,
  max_abs_corr, nearest_family_id, nearest_family_status,
  nearest_family_cumulative_n_trials, decision(ASSIGN|MINT|NEEDS_HUMAN|SKIP_RECOMMENDED),
  inherited_n_trials, inherited_K, provisional_new_family(bool),
  human_review_items: [mechanism_novelty, refuted_family_twist_justification,
                       borderline_distinctness], reason

I27(接 I26 後):
  「自動發想鑄 family 的決定必須讀 ledger 的 family status + family-cumulative n_trials;
   候選 signal 與任一 enabled/occupied 參照 signal 的 |相關| >= HARD_ASSIGN_CORR 時
   一律 ASSIGN(繼承額度 + K),**不得 MINT**;MINT 僅在低於 borderline 且經人審確認新機制時
   成立。守護 R6.3/R7.4;測試:tests/unit/test_pipeline_family_minting.py」

PERMITTED FILES (only edit these):
- backtesting/pipeline_family_minting.py            (新增)
- scripts/run_pipeline_family_minting_check.py      (新增)
- tests/unit/test_pipeline_family_minting.py        (新增)
- docs/INVARIANTS.md                                (僅加 I27)
- backtesting/pipeline_checkpoint1.py               (僅允許「抽出共用 ledger 解析函式」的最小 refactor,不改其決策行為/輸出)
- docs/change_manifests/2026-06-30-family-minting-checker.md  (新增,鏡像 checkpoint① manifest 的 R6.3/R7.4 doc-impact)

FORBIDDEN (do not touch):
- src/okx_quant/strategies/ , signals/ , risk/ , portfolio/ , execution/
- backtesting/cpcv.py , walk_forward.py , differential_validation.py , replay.py
- analytics/dsr.py ; config/risk.yaml ; 任何 deployment/demo/shadow/live gate
- HYPOTHESIS_LEDGER.md / EXPERIMENT_REGISTRY.md 的裁決或 n_trials **值**(只讀不改)
- 既有 results/** artifact

SCOPE LIMIT:
只做「讀 candidate+refs+ledger → 算相關 → 依門檻決策 → 寫 json」的純決策層。不接發想前段、
不抓參照 signal、不改門檻常數以外的統計演算法。門檻為 config 常數,標 ponytail 註解寫明
ceiling 與調整路徑。decision 是 advisory,SKIP_RECOMMENDED/NEEDS_HUMAN 不自動丟棄候選,
最終由 checkpoint① #9 / per-batch 稽核人審。

REQUIRED ON COMPLETION:
- List changed files
- Run: pytest tests/unit/test_pipeline_family_minting.py + make docs-check
- 補 change manifest(新增 I27 = 業務規則治理變更,鏡像 2026-06-30-checkpoint1-automation.md 的審查)
- Commit with AI-Origin: Codex trailer

ACCEPTANCE CRITERIA:
- [ ] candidate 與某參照幾乎相同(corr≈1.0)→ ASSIGN,且**不可 MINT**。
- [ ] candidate 宣告 NEW 但與 F-FUNDING-CARRY 參照 corr≈0.95 → ASSIGN/SKIP_RECOMMENDED
      (F-FUNDING-CARRY 已 refuted),**不得 MINT**——這是 K-規避守門測試。
- [ ] candidate 與所有參照近正交(corr≈0)且宣告 NEW → MINT 資格,human_review_items 非空。
- [ ] ASSIGN 時回填的 family_cumulative_n_trials 與 EXPERIMENT_REGISTRY 對得上(重用 checkpoint① 解析)。
- [ ] borderline corr(0.70–0.90)→ NEEDS_HUMAN。
- [ ] I27 入 INVARIANTS.md,測試守護存在並通過。
```

## 7a. 跟進任務:把 K 來源接進 checker（Codex,一步）

**背景**:§7 checker 目前 `inherited_K = inherited_n_trials`(有 ponytail 註解標記的已知缺口)
——把 K(重試次數,上限 2)誤當 n_trials(grid 累計,可達 48)。**來源已補**:
`docs/EXPERIMENT_REGISTRY.md` 的 *Family K-budget* 表(per-family `K_used`/`K_limit`,
rows 以 `| F-` 開頭,既有 `| E-` parser 會略過、不受影響)。這個任務只做接線。

```text
Task: family-minting checker 讀真實 K_used,不再用 n_trials 冒充
PERMITTED FILES (only edit these):
- backtesting/pipeline_checkpoint1.py    (擴 family_registry_from_text:解析 Family K-budget 表
                                          → 每 family k_used/k_limit;沿用既有「| F-」前綴判別)
- backtesting/pipeline_family_minting.py (用真實 k_used 取代 inherited_n_trials;輸出加
                                          k_used / k_limit / at_k_limit;移除/修正 inherited_K 冒充)
- tests/unit/test_pipeline_family_minting.py (加測試:見驗收)
- docs/INVARIANTS.md                     (僅在 I27 措辭需同步時)
FORBIDDEN:
- 改 ASSIGN/MINT/SKIP/NEEDS_HUMAN 決策門檻或邏輯;trading-core;gates;
  EXPERIMENT_REGISTRY 的 K_used 值(只讀,不改)
SCOPE LIMIT:
只接線「讀 K-budget 表 → 報告真實 K」。決策邏輯不動。
ACCEPTANCE CRITERIA:
- [ ] F-FUNDING-CARRY ASSIGN → 輸出 k_used=1, k_limit=2(不再是 inherited_K=48)。
- [ ] F-XS-MOMENTUM → at_k_limit=true(k_used==k_limit==2)。
- [ ] F-PAIRS-OU / F-SENTIMENT → k_used=0。
- [ ] inherited_K 冒充移除;既有 6 個 §7 測試仍綠。
- [ ] make docs-check 過;補 change manifest。
```
