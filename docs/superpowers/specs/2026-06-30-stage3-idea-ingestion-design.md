---
status: draft
type: design
owner: human
created: 2026-06-30
last_reviewed: 2026-06-30
expires: none
superseded_by: null
---

# Stage 3「從 0 發想」ingestion 設計 spec(draft)

> 對應 [strategy-research-pipeline-design.md](2026-06-25-strategy-research-pipeline-design.md)
> 路線圖的 **Stage 3 解鎖**:「Stage 2 穩定 + 排程 cron/loop 自動執行 family 預算與
> 停止條件 + 文獻搜索 ingestion 加品質過濾(編排 C)」。
> 目標:讓管線**不靠人預先放進 backlog**,自己從文獻/機制空間產生候選,一路跑到回測。
> 本 spec 把核心張力「**便宜發想 × 誠實 n_trials**」的防護機制定清楚,並列出待使用者
> 決策的 fork。`status: draft`,不改任何 demo/shadow/live gate。
> **前置依賴**:本階段預設 [checkpoint1-automation-contract](2026-06-30-checkpoint1-automation-contract.md)
> (Stage 2 解鎖)已完成——沒有自動 checkpoint①,自動發想會把人淹沒。

## 1. 問題 / 動機

現況 Stage 1 的「文獻→假設」其實是「把既有 backlog 條目展開成 spec」,**不是文獻搜索**
(見原 spec 第 119 行)。候選 S5/S6/S7、C1/C2/C3 全由人放進 backlog。要走到「從 0 全自動
發想」,缺的是一個**會自己產生新經濟機制假設**的 ingestion 前段。

## 2. 核心張力:便宜發想 × 誠實 n_trials = 假陽性工廠(除非…)

原 spec 第 27–32 行已點破:這是全專案 overfitting 風險最高的活動,而且「真正槓桿是
**先驗品質**,不是試更多次」——誠實計數下,沒有真 edge 的想法期望通過數 ≈ 0,有真 edge
的想法期望嘗試 ≈ 1/(真 edge 基率)。

**LLM 發想極便宜**,所以全自動發想會把 N(每日產生的假設數)從個位數推到上百。多重檢定
的數學是:**只要 n_trials 帳算得滴水不漏,便宜發想不會傷害你**——DSR/PSR 會自動把海量
低先驗想法的期望通過數壓到 0。**會傷害你的是「測了卻沒計入 n_trials」的洩漏**:自動發想
最大的新風險,就是它「悄悄丟掉」沒過的想法而不計帳,或用「無限新 family」稀釋 deflation。

所以本 spec 的全部重點 = **不是讓發想更聰明,而是讓「凡碰過回測的想法都誠實入帳、且
family 不能被濫鑄」**。

## 3. 發想來源(設計空間 + 建議)

| 選項 | 說明 | overfitting 風險 | 建議 |
|---|---|---|---|
| A 文獻 ingestion | 抓 paper/部落格/SSRN → 抽「經濟機制 + 可測 signal」→ 落成 H-xxx | 低(機制有外部來源,先驗可辯護) | **採用** |
| B 機制分類法枚舉 | 維護一個經濟機制 taxonomy(carry / momentum / mean-rev / 微結構 / 事件…),系統化展開未覆蓋格;**初始清單見 [mechanism-taxonomy.md](2026-06-30-mechanism-taxonomy.md)** | 中(枚舉有限,可控) | **採用(與 A 並行)** |
| C 自由資料挖掘 / LLM 無錨發想 | 讓模型對資料自由找 pattern 產 signal | **極高**(無經濟先驗 = 純過擬合產生器) | **不採用**(除非使用者顯式批准且納入超嚴 n_trials) |

**理由**:A+B 的共同點是「每個假設都帶可辯護的 ex-ante 經濟機制」,這正是「先驗品質」這個
真槓桿。C 沒有先驗,送進自動回測等於把 deflation 之外的防線拆掉。

## 4. 防護機制(本 spec 的核心)

1. **family-before-backtest**:任何自動產生的想法,在花任何回測 compute 前,**必須先被指派
   到一個經濟機制 family 並登記先驗**(機制敘述 + 為何淨成本後該有 edge)。沒有 family =
   不准進 Stage 2。

2. **family minting gate(防 K 規避的關鍵)**:自動發想最大的作弊面是「鑄無限新 family 把
   K 歸零、把 deflation 稀釋」。所以**鑄新 family 必須過 distinctness gate**(重用 Stage 2
   §(b) 相關性上限 + checkpoint① #9 判定;裁決基準 =
   [mechanism-taxonomy §3](2026-06-30-mechanism-taxonomy.md)):
   - 與既有 family 經濟上不夠不同 → **不鑄新 family**,該想法**繼承最近 family 的 n_trials
     額度與 K 計數**(當重試處理)。
   - 通過 distinctness → 鑄新 family(新預算,K 歸零),但**該決定要落帳供事後人審**。
   - `// ponytail: distinctness 判定重用既有 Stage 2 distinctness check,不另造模型`

3. **凡碰 Pass-A 即入帳**:任何到達 Pass-A 便宜預篩的想法(含自動產生、隨後被砍的輸家)
   **trial 一律計入該 family 的 n_trials**。自動發想不得「試了再悄悄丟」。

4. **批次預先登記延伸到自動候選**:沿用原 spec 鎖定的「批次預先登記」——driver 先把這一輪
   自動產生的整批候選寫進 JSON 批次狀態檔 + ledger,**才開始跑**;事後不能把沒過的拿掉。
   JSON 批次檔必須記錄每個「碰過回測的 idea」,checkpoint 時對帳同步回永久 ledger。

5. **prior plausibility gate(Stage 2 延伸)**:在花 Pass-A 前,自動候選要先過「先驗合理性」
   ——機制已敘述、有 ex-ante 淨成本後 edge 理由、且**不是某個已 refuted family 的換皮**
   (查 ledger:該 family 若已 shelved/refuted 且無新機制,直接 skip,不重燒 compute)。

6. **compute / 產量上限**:每輪自動發想有硬上限——**候選數 ≤ 15(2026-06-30 決策)** +
   runtime(無靜默預設,啟動時填),超過乾淨中止。防止自動迴圈失控狂燒。
7. **跨輪回饋入帳鐵則(決策 4 的硬條件)**:採用 RD-Agent 式跨輪知識回饋後,**任何由回饋
   偏置而生、且到達 Pass-A 的想法,一律計入其 family 的 n_trials**;family 預算與 K 上限照舊。
   回饋只准影響「下一個試什麼」的順序/優先,**不准繞過入帳**。checkpoint① 的 I26 對帳必須把
   回饋衍生的 trial 算進去。沒有這條,跨輪回饋就是把測試集資訊灌進搜索的多重檢定放大器。

## 5. 仍然必須人審(全自動下也不消失,升級為 per-batch / per-policy)

- **idea-source corpus / taxonomy 批准**:機器能鑄想法的「宇宙」(讀哪些文獻來源、taxonomy
  長怎樣)由人定。這是把先驗品質的源頭控制權留在人手上。
- **family-minting 稽核**:週期性抽查「自動鑄的新 family 是否真的經濟獨立」,防 relabel 繞 K。
- **成本真實性判斷**:gate flag 全過 ≠ 模型可信(C2 0.247% vol「太平靜」那類),人看。
- **發布(step 5)**:不變,使用者的第二關,碰資金與 deployment gate。

對照 [checkpoint1-automation-contract](2026-06-30-checkpoint1-automation-contract.md):那份把
checkpoint① 的*機械項*自動化;本 spec 確認其*判斷項*在全自動下升級為批級稽核,而非移除。

## 6. 編排(roadmap 編排 C)

- cron/loop driver 觸發 → 自動發想一批 → 預先登記 → 對每候選跑 Stage 2→3 →
  checkpoint① auto checker 擋機械硬傷 → 把 `NEEDS_HUMAN` / auto-PASS 的彙整成短名單 →
  人只審判斷項 + 發布。
- 停止條件沿用原 spec:批次跑完 / 撞 compute 上限 / family 撞 K。
- `// ponytail: driver 用 cron/loop + 既有 subagent-driven skill,不造新編排框架`

## 7. 外部公開發想器借鏡(prior art,2026-06)

搜了現有公開的自動量研框架,結論:**借模式,不搬框架**。它們多為日頻股票
factor/model 範式(Qlib / CSI300、cross-sectional IC),本 repo 是 crypto-perp、
event-driven replay,且 gate 更嚴(DSR/PSR ≥ 0.95、ct_val provenance、differential
validation、idealized-fill 排除)。整包接進來會跟現有架構打架並**稀釋 gate**。

| 工具 / 論文 | 它做什麼 | 我們採用 | 理由 |
|---|---|---|---|
| **Microsoft RD-Agent / R&D-Agent-Quant**(五單元閉環:Specification→Synthesis→Implementation→Validation→Analysis) | LLM 自動產 factor/model 假設 → 實作(Co-STEER)→ 回測 → 分析 → 回饋下一輪 | **借架構模式**(我們 Stage1/2/3/checkpoint① 已同形)+ 採其 3 個具體機制(下) | 不搬 codebase:Qlib 日頻股票範式,gate 比我們鬆 |
| **AlphaAgent**(regularized exploration vs alpha decay) | LLM alpha mining,用 originality(AST 相似度)+ complexity(符號長度/參數數)+ hypothesis alignment 正則化抗過擬合/衰退 | **借 3 個正則化原則**(下) | 公式化 alpha 的 AST 不直接套較複雜的策略,但原則可轉 |
| **AlphaGen / gplearn / GP·RL 公式化 mining** | 用 RL/基因規劃自動產公式 alpha | **明確不採用** | 多份來源一致:GP/RL 傾向產複雜、不可解釋、過擬合 factor——正是 §3 拒絕的「Option C 自由挖掘」。外部證據反證「先驗品質 > 試更多次」 |
| **vectorbt(+PRO)** | 向量化大規模 grid/CV,秒級跑上萬組合,內建 CV decorator + 抗過擬合啟發 | **採為 Pass-A 引擎**(已是 differential validation reference 依賴) | 純重用,已安裝;Pass-A 便宜預篩正需要它 |
| **OpenBB Workspace / Copilot / AI SDK** | 「connect once, consume everywhere」資料層 + MCP server 給 agent | **參考其資料層模式**(選用,非必須) | 已有 DB + market_data ingest;OpenBB 是文獻/另類資料 reach 的可選 MCP 來源,不新增強依賴 |

**從 RD-Agent 採的 3 個具體機制(補強 §4 防護):**
- **IC 去重門檻**:RD-Agent 把 `IC_max ≥ 0.99` 的 factor 當冗餘剔除。→ 把 §4.2
  family-minting distinctness gate 從純質性升級為**可量化 backstop**:候選 signal 與既有
  enabled signal 的相關/IC 超過門檻 → 不鑄新 family(當重試處理)。
- **LLM 不得看原始市場資料 / 切分邊界**:RD-Agent 刻意讓 LLM 看不到 raw market data 與
  temporal split。→ 加一條**發想防火牆**:idea-generation agent 只吃經濟機制 + 文獻,
  **不得餵入 OOS 區段資料或 fold 邊界**;從源頭擋掉「用測試集資訊發想」這種多重檢定洩漏
  (補強 leak gate / I8 / I24)。
- **Analysis 單元的跨輪知識累積 + Thompson 排程**:RD-Agent 用持久知識庫 + contextual
  Thompson sampling 把上一輪結果回饋到下一輪。→ **已採用(2026-06-30 使用者,決策 4)**,
  但**這正是多重檢定洩漏入口**(生成被回測結果條件化 = 測試集影響搜索)。採用硬條件:回饋
  產生的每個碰 Pass-A 的想法**一律計入 family n_trials**,family 預算與 K 照舊;否則知識回饋
  會偷偷膨脹搜索強度而不入帳。詳見 §4.7。

**從 AlphaAgent 採的 3 個正則化原則(補強 §4 / §5):**
- **originality / 抗 crowding-decay**:把「與既有 / 已衰退 / 已 refuted 機制的接近度」當降權
  因子(補強 §4.2 + §4.5)。
- **complexity → 直接餵 n_trials**:參數數 / 自由度越高 = grid 越大 = family n_trials 越高。
  把**參數數列為 prior-plausibility gate 的顯式輸入**(§4.5);parsimony 直接換成更低的
  deflation 負擔——比 AlphaAgent 的對數懲罰更硬,因為我們本來就誠實計 n_trials。
- **hypothesis alignment**:「實作出來的 signal 是否真的實現了所宣稱的經濟機制」——列為
  checkpoint① 的人審 consistency 項(§5),部分可自動(spec 欄位齊全 + 機制↔signal 對照)。

**RD-Agent 具體落地邊界(看了 repo,不只論文):**
- `pip install rdagent`,但 **Linux-only + Docker required + LiteLLM 後端**;本 repo 跑
  Windows,直接接有營運摩擦。
- finance 迴圈**硬綁 Qlib + 日頻股票**(cross-sectional IC 排序);只有 general / Kaggle /
  LLM-finetune 場景與 Qlib 解耦。把我們的 crypto-perp / funding / ct_val 資料硬塞進 Qlib
  格式不划算。
- 它的 gate(walk-forward + IC 去重 + OOS)**比我們鬆**:沒有 DSR/PSR ≥ 0.95、沒有 ct_val
  provenance、沒有 differential validation、沒有 idealized-fill 排除。**不能讓它的
  「promotion」概念漏進來。**
- **安全採用邊界 = 只當「想法來源」,不當「驗證者」**:可考慮只跑它的 **Synthesis(發想)
  半邊**,把產出的假設餵進我們 backlog,再走我們自己的 Stage 2→3 + 全 gate。它的回測/驗證
  半邊對我們是**冗餘且較弱**,丟掉。它「2× ARR、單次 < $10」也佐證便宜發想可行——但便宜
  正是 §2 那個張力的來源,不是放鬆 gate 的理由。

> 一句話:外部最先進的自動發想器(RD-Agent)和我們同形,但**它們的護欄比我們鬆**;
> 我們要做的不是抄它的迴圈,而是把它驗證過的好機制(IC 去重、LLM 資料防火牆)接進
> 我們**更嚴的** n_trials / DSR / ct_val gate 上。GP/RL 公式化 mining 的過擬合教訓,則是
> 我們堅持拒絕「自由挖掘」的外部佐證。

**Sources:**
[microsoft/RD-Agent](https://github.com/microsoft/rd-agent) ·
[R&D-Agent-Quant (arXiv 2505.15155)](https://arxiv.org/html/2505.15155v2) ·
[AlphaAgent (arXiv 2502.16789)](https://arxiv.org/html/2502.16789v2) ·
[vectorbt](https://github.com/polakowo/vectorbt) ·
[vectorbt PRO optimization](https://vectorbt.pro/features/optimization/) ·
[OpenBB AI SDK](https://docs.openbb.co/workspace/developers/openbb-ai-sdk)

## 8. 已定決策(locked,2026-06-30 使用者)

| # | 決策 | 選擇 | 後果 |
|---|---|---|---|
| 1 | 啟用順序 | **checkpoint① 自動化優先**,穩了再開發想 | 先實作 [checkpoint1-automation-contract](2026-06-30-checkpoint1-automation-contract.md);ingestion 為其下游 |
| 2 | 發想來源 | **文獻 + 機制 taxonomy;禁止自由挖掘(Option C 不採用)** | 每個想法必帶可辯護經濟機制;RD-Agent 只借機制(IC 去重 / 資料防火牆),**不**當想法來源 |
| 3 | 每輪硬上限 | **≤15 候選/輪** | driver 啟動參數封頂 15;超過乾淨中止;runtime 上限仍須啟動時填(無靜默預設) |
| 4 | 跨輪知識回饋 | **採用**(RD-Agent 式) | 硬條件:回饋產生且碰 Pass-A 的每個想法**一律計入 family n_trials**——見 §4.7,非選配 |

**仍延後(預設值,使用者未否決)**:family-minting 稽核頻率 = **每批都稽核**(初期);
文獻 corpus 來源清單 / 維護方式 = 等實作 ingestion 前段時再定。

**已草擬(2026-06-30)**:決策 2 的 B 來源「機制 taxonomy 初始清單」+ family-minting 裁決基準
已寫成 [mechanism-taxonomy.md](2026-06-30-mechanism-taxonomy.md)(17 個 family:7 occupied 多數
已 refuted、4 untested-documented[S1/S2/S8/S10]、6 frontier;標了資料可得性與 distinctness 鄰居)。
ingestion 剩餘可實作子件 = (a) family-minting distinctness checker、(b) 文獻 corpus 前段。

> ⚠️ 決策 4 把原建議「先不採用」的跨輪回饋打開了。可行,但它讓 **n_trials 誠實對帳從
> 「重要」升級為「管線安全的單點命脈」**:回饋會被回測結果條件化(測試集影響搜索),
> 唯一擋住多重檢定爆量的就是「凡碰 Pass-A 即入帳 + family 累計 + K 上限」。因此 §4.7 是
> 硬條件,且 checkpoint① 的 n_trials 對帳(I26)現在**必須涵蓋回饋衍生的 trial**。

## 8. 重用 vs 新增(ponytail)

**重用**:family ledger 協定、n_trials 累計、Stage 2 distinctness/feasibility checker、
checkpoint① auto checker、cron/loop + subagent-driven skill、批次預先登記機制、永久 ledger。

**新增(最小)**:
- 一個 idea-ingestion 前段(文獻→機制抽取 → H-xxx 草稿 + family 指派),產出沿用既有
  HYPOTHESIS_LEDGER 格式。
- family-minting distinctness gate(重用 Stage 2 distinctness,加「不過則繼承額度」分支)。
- prior plausibility gate(Stage 2 feasibility 加一條「已 refuted family 換皮偵測」)。
- corpus / taxonomy 設定檔(人維護)。

## 9. scope / role

- 本文件為設計/治理文件,Claude 可寫。ingestion 前段的研究邏輯屬 Claude/研究;trading-core、
  回測引擎、checker 實作由 Codex。
- 本管線只產出「通過既有 gate 的短名單」,**不改任何 deployment/demo/shadow/live gate**,
  發布權在使用者。全自動發想**放大**的是搜索規模,不是放鬆任何 gate。
