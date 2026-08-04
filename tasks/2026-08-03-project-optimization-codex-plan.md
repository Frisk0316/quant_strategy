---
status: current
type: task
owner: claude
created: 2026-08-03
last_reviewed: 2026-08-03
expires: none
superseded_by: null
---

# 專案最佳化企畫書 — 交付 Codex 實作（2026-08-03）

來源:一次全庫多代理稽核(6 維度 × 對抗式驗證,12/13 代理完成;完整性
critic 因額度中斷,未涵蓋面見文末「未稽核範圍」)。所有列出的發現皆經第二個
代理重讀原始碼 CONFIRMED;三條最高風險項(路徑穿越 rmtree、auth fail-open、
`reduceOnly` 未送出)由 Claude 本人再次覆核程式碼無誤。

## 給 Codex 的總則(先讀)

- 本檔是計畫,不是授權。**WS-C(交易安全)整組會改到
  `execution/`、`risk/`、`portfolio/`,屬受保護區,必須先取得使用者對「該項」
  的明確授權才能動手**;未授權前只做 WS-A/B/D/E。
- 每一條動到 PnL/fee/funding/sizing/fills/gates 的變更 =
  商業規則變更 → 依 `docs/DOC_IMPACT_MATRIX.md` 建立 Change Manifest,並跑
  `python scripts/docs/check_doc_impact.py --strict`。下方逐項標了 `Manifest:Y/N`。
- 本機無 `make`。驗證指令一律用下方 PowerShell 等價寫法(這也是 WS-E1 要
  補進 RUNBOOK 的東西)。單元測試父/lab 兩套要分開跑。
- 每項獨立成 commit,scope 只做該項,不順手重構鄰近程式。commit 帶
  AI-Origin trailer(見 `docs/AI_WORKFLOW.md`)。
- 完成後回報 `AGENTS.md` 的標準區塊(Files changed / Tests run / Docs updated
  / Risks / Rollback)。

## 優先順序(依風險,由高到低)

0. **WS-F1 Telegram 指令通道無驗證**(high,**免授權**,見 §WS-F)— 任何人可
   `/kill` 停止交易、`/reset` 清空風控並恢復滿倉。修補點在 `monitoring/`,
   不在受保護路徑內。建議與 WS-A 同一批做。
1. **WS-A 網路/API 曝險** — 有 1 條 critical(資料目錄被遠端清空)。先做。
2. **WS-B 憑證外洩** — 真實下單權限的 OKX key 與 live 路徑共用。
3. **WS-C 交易安全** — 引擎 live 路徑的風控多為裝飾用、失效方向錯誤。
   **需逐項授權 + Change Manifest**,是這份稽核最重的部分。
4. **WS-D 效能** — 資料管線 O(n²) / iterrows,非金流路徑,可安全並行。
5. **WS-E 協作架構/可維護性** — 文件漂移、無 make 驗證、8k 行單體檔。
6. **WS-F 第二輪補稽核** — DB 壓縮/schema 漂移、排程 harness 過寬、手冊頁
   消毒、測試網路隔離。其中 F2 在 `execution/` 需授權。

> 稽核覆蓋度:兩輪共 11 個面向、24 個代理、findings 全數經第二代理對抗式驗證。
> 第二輪確認 git 歷史無真實憑證外洩、無 notebooks、測試不打網路(詳見 §WS-F 末)。

---

## WS-A — 網路與 API 曝險(資安)

### 診斷
引擎儀表板 API 預設綁 `0.0.0.0` 且 `API_KEY` 未設時 auth **fail-open**
(只印 warning 就放行);standalone server 對破壞性路由完全沒掛 auth;
`DELETE /api/data/pairs/{inst_id}` 的 `inst_id` 只做 strip/upper 未驗證,
`..` 會讓 `shutil.rmtree` 刪掉整個 `data/` 樹;job-status API 把含密碼的 DSN
原封回傳。docker-compose 只有 app port 綁全介面。

### Files to change
- `src/okx_quant/api/server.py`、`src/okx_quant/api/routes_data.py`、
  `src/okx_quant/api/routes_backtest.py`、`scripts/run_server.py`、
  `docker/docker-compose.yml`
### Files NOT to touch
- `backtesting/`、`src/okx_quant/{strategies,signals,risk,portfolio,execution}/`

| # | Sev | 檔案:行 | 問題 | 修法 | Manifest |
|---|-----|--------|------|------|----------|
| A2 | **critical** | routes_data.py:437 | `inst_id='..'`/`.` → `rmtree(data/…/..)` 清空資料樹 | 過 `validate_artifact_id`(已存在於 `backtesting/artifact_rows.py:40`)或 `^[A-Z0-9]+(-[A-Z0-9]+)+$`,失敗回 400;刪前用 `resolve_artifact_child` 斷言容納 | N(安全修補) |
| A1 | critical | server.py:46-52,173; engine.py:413 | 預設綁 0.0.0.0 + auth fail-open | `host` 預設 `127.0.0.1`;非 loopback 綁定卻無 `API_KEY` 時**啟動即拒絕**(不要 per-request warning 放行) | N |
| A4 | high | run_server.py:52-70 | standalone server 破壞性路由零 auth、`--host 0.0.0.0` 無補償、`/api/docs` 曝露 | 對 backtest/data/config router 掛 `Depends(verify_api_key)`;非 loopback 需 `--allow-remote` + 已設 `API_KEY` 才啟動;`/api/docs` 同條件 gate | N |
| A3 | high | routes_backtest.py:468-480 | job `command` 內含 `--dsn postgresql://quant:<pw>@…`,經 `/run/status`、`/run/jobs` 明文回傳 | 存進 `_run_jobs` 前遮蔽 `--dsn` 後的值;真實 DSN 只走子行程 `env`(DATABASE_URL 已在 env),不進 argv | N |
| A5 | medium | docker-compose.yml:12,19 | app port `8080:8080` 綁全介面(其他服務都 127.0.0.1);`API_KEY` 空字串觸發 fail-open | 改 `127.0.0.1:8080:8080`;`API_KEY`/`TIMESCALE_PASSWORD`/`GRAFANA_PASSWORD` 用 `${VAR:?...}` 必填,缺就 compose 拒起 | N |
| A6a | low | server.py:127-136 | `/api/manual`、`/api/progress` 未掛 api 依賴,可無憑證讀內部狀態 | 補 `dependencies=api_dependencies`,或註明為何刻意公開 | N |
| A6b | low | server.py:51 | 非 ASCII `X-API-Key` 使 `compare_digest` 丟 TypeError → 500(而非 401) | 比較 bytes:`x_api_key.encode('utf-8','surrogateescape')` | N |
| A6c | low | server.py:55-60,146 | WS key 走 query string 且 fail-open | 改由 header/cookie 帶 key;非 loopback + 未設 key 時 close 4001 | N |
| A6d | low | server.py:93-101 | `allow_credentials=True` + `ALLOWED_ORIGINS` 未擋 `*` | 偵測 `*` 或無 scheme 的 origin 在 credentials=True 時拒啟動;收斂 allow_methods | N |

### Codex Task(A1+A2+A3+A4+A5,一組 PR)
```text
Task: 修補 API/網路曝險:路徑穿越、fail-open auth、DSN 洩漏、standalone 無 auth、compose 綁定
Plan source: tasks/2026-08-03-project-optimization-codex-plan.md §WS-A

PERMITTED FILES:
- src/okx_quant/api/server.py
- src/okx_quant/api/routes_data.py
- src/okx_quant/api/routes_backtest.py
- scripts/run_server.py
- docker/docker-compose.yml
- tests/unit/  (新增/擴充回歸測試)

FORBIDDEN: src/okx_quant/{strategies,signals,risk,portfolio,execution}/, backtesting/, config/risk.yaml

SCOPE LIMIT: 只做 §WS-A 表列各項;不重構鄰近路由。

REQUIRED ON COMPLETION:
- git diff --stat
- 跑並貼尾段:
    python -m pytest tests/unit/test_routes_data_delete.py tests/unit -k "auth or delete or dsn" -q
- 更新 docs/FAILURE_MODES.md(新增「API path-traversal on inst_id / fail-open bind」bug class,
  強化 docs/INVARIANTS.md 對應不變式),及 docs/KNOWN_ISSUES.md 關掉 F52 相關已修部分。

ACCEPTANCE CRITERIA(binary):
- [ ] DELETE /api/data/pairs/%2e%2e、/. 、/../ 皆回 400,無 rmtree 觸及 data/ 外或上層
- [ ] 非 loopback 綁定 + 空 API_KEY → 程序啟動即失敗(有測試)
- [ ] GET /run/status、/run/jobs 回傳的 command 不含資料庫密碼(有測試)
- [ ] run_server.py 對 backtest/data/config 路由要求 API key;--host 0.0.0.0 無 key 時拒起
- [ ] docker-compose app port 綁 127.0.0.1;缺三個必填變數時 compose 拒起
- [ ] Diff 僅含 permitted 檔
```

---

## WS-B — 憑證處理(資安)

### 診斷
具**真實下單權限**的 OKX key 與 demo smoke、`download_okx_data.py(demo=False)`、
`engine.py` 的 `OKXBroker(demo=cfg.is_demo())` 共用同一組環境變數,單一 mode 設定
失誤即以真金下真單(已有 2026-07-31 隔離 task,尚未實作)。FRED/Nasdaq key 以 URL
query 傳送,`raise_for_status()` 例外含完整 URL,被 `ingest_external.py` 寫進 DB 的
`error_message`/`last_error` 永久留存。另有 `changeme`/`admin` 預設密碼、
`OKXSecrets` 純 str(任何 repr/dump 會印出金鑰)。

### Files to change
- `.env.example`、`scripts/run_okx_demo_smoke.py`、
  `src/okx_quant/data/external_clients/fred.py`、`.../nasdaq_data_link.py`、
  `scripts/market_data/ingest_external.py`、`src/okx_quant/core/config.py`、
  `src/okx_quant/monitoring/telegram_alert.py`、`config/settings.yaml`、
  `docker/docker-compose.yml`、`src/okx_quant/execution/binance_testnet/futures_client.py`
  、`src/okx_quant/execution/deribit_live/private_client.py`

| # | Sev | 檔案 | 問題 | 修法 | Manifest |
|---|-----|------|------|------|----------|
| B1 | **high** | run_okx_demo_smoke.py:48; .env.example | live 權限 key 與 demo/live 路徑共用(已有隔離 task 未實作) | 實作 `tasks/2026-07-31-okx-demo-credential-isolation-codex-tasks.md`:新增 `OKX_DEMO_*`,smoke 只讀 demo key(`dotenv_values` 模式),缺就 fail-closed;`demo=True` 寫死 | N(資安隔離) |
| B2 | medium | fred.py:39; nasdaq_data_link.py:26-38; ingest_external.py:353-364 | API key 隨例外訊息寫入 DB 錯誤欄與 traceback | client 內攔 `httpx.HTTPStatusError` 重拋 sanitized 訊息;或在 ingest 寫入前 regex 遮 `api_key=…` | N |
| B4 | low | settings.yaml:28; compose:11,43,92; ~14 檔 DSN 預設 | `changeme`/`admin` 硬編預設密碼 | compose 去掉 `:-changeme`/`:-admin` 改必填;程式 fallback 讀 `DATABASE_URL`/config 不內嵌字面密碼;字面值只留 `.env.example` | N |
| B3a | low | config.py:40-44 | 純 str 金鑰,repr/model_dump 明文 | 五欄改 `SecretStr`,建構點呼叫 `.get_secret_value()`(engine.py:64-66,92-94,158-161,270-272) | N |
| B3b | low | telegram_alert.py:22,35,54 | bot token 在 URL,例外文字被 log | log `type(e).__name__` + `str(e).replace(token,'***')`;不對這些請求加 `raise_for_status` | N |
| B5 | low | futures_client.py:60; private_client.py:49-57 | `from_env` 的 `.env` 依 cwd 解析,可能載到別的 .env(已列 KNOWN_ISSUES) | 預設 anchor 到 repo root(`Path(__file__).resolve().parents[N]/'.env'`)或要求絕對路徑 | N |

### Codex Task(B1 先單獨做,B2-B5 可合一 PR)
```text
Task: OKX demo 憑證隔離 + 外部 API key 遮蔽 + 移除預設密碼 + SecretStr
Plan source: tasks/2026-08-03-project-optimization-codex-plan.md §WS-B

PERMITTED FILES: 見上表各檔 + tests/unit/
FORBIDDEN: strategies/signals/risk/portfolio/execution(除 futures_client.py from_env anchoring 一行)/、config/risk.yaml

REQUIRED ON COMPLETION:
- python -m pytest tests/unit/test_okx_demo_smoke.py tests/unit -k "cred or secret or redact" -q
- 更新 .env.example、docs/RUNBOOK.md 憑證段、docs/KNOWN_ISSUES.md(關 from_env anchoring)

ACCEPTANCE CRITERIA:
- [ ] run_okx_demo_smoke.py 只讀 OKX_DEMO_*;缺 demo key → 明確 fail-closed 訊息,demo=True 寫死
- [ ] 模擬 FRED/Nasdaq 4xx,persisted error_message 不含 api_key 值(有測試)
- [ ] compose 缺密碼變數即拒起;程式碼無 quant:changeme 字面(grep 空)
- [ ] OKXSecrets 為 SecretStr;str(cfg) / model_dump 不外洩金鑰(有測試)
```

---

## WS-C — 交易安全(需逐項授權 + Change Manifest)

> **停!** 本組每一項都會改 `execution/`、`risk/`、`portfolio/`——受保護區。
> Codex 依 `AGENTS.md` 硬規則,**須先有使用者對「該項」的明確授權**才能動,且每項
> 需 Change Manifest(`docs/CHANGE_MANIFEST_TEMPLATE.md`)+ `--strict` docs-impact +
> 更新 `docs/FAILURE_MODES.md`/`docs/INVARIANTS.md` + 新增守護測試。修完**不得**宣稱
> live/demo 就緒(仍受 `docs/ai_collaboration.md` gate 管)。

### 診斷(一句話)
引擎 live 路徑的風控在「該作動時」多半失效:硬停不撤單不平倉、回撤只在成交時更新
(未實現虧損不觸發)、無啟動對帳、CircuitBreaker 無人餵資料、WS 靜默斷線無偵測、
mid 取自原始 delta 而非維護中的訂單簿、`reduceOnly` 未送交易所、ctVal fallback 錯 10 倍。

> 行號已於 2026-08-03 對照 `6bdafa0` 重新驗證(paper-demo 批次 `1992ac2` 動過
> `broker.py`/`portfolio_manager.py`/`engine.py`,舊行號已失效)。

| # | Sev | 檔案:行(已驗證) | 問題 → 後果 | 修法 |
|---|-----|--------|-------------|------|
| C1 | **high** | engine.py:339; state.py:85 | 回撤/日虧只在 on_fill 更新,`tick_risk_snapshot` 是 `pass` → 未實現虧損不觸發 5%/15% 鐵律 | 週期(每 2s)以 `positions.get_equity()`(已是 mark-to-market)餵 `dd_tracker.update`,由該迴圈觸發軟/硬停 |
| C2 | **high** | engine.py:442-446; risk_guard.py:194; telegram:63 | 硬停/關機/`/kill` 只設旗標,不撤 resting 單、不平倉 → 全曝險無人看管 | 關機與 hard-stop:掃 `order_manager.get_pending()` 逐一撤單,hard-stop 額外(旗標控)`broker.close_all()`;加測試 |
| C3 | **high** | broker.py:88-97 | `reduceOnly` 未送 OKX,但 RiskGuard 因它放行 kill/fat-finger/倉位上限 → 「只減倉」單可能開/翻倉 | `place_order` 帶 `reduceOnly="true"`(及 posSide);加測試斷言 kwargs 含旗標 |
| C4 | **high** | broker.py:135-137 | submit 逾時(交易所已收單)回 None → 孤兒掛單、重新報價成雙倍曝險 | 區分交易所拒單 vs 傳輸例外;傳輸例外時以 clOrdId 查單對帳或撤單,鏡像 deribit_live F59 |
| C5 | **high** | engine.py:121-126; portfolio_manager.py:349 | get_instruments 失敗即 fabricates `ctVal=0.01`(ETH 實為 0.1)→ 下單量錯 10 倍且 notional 低估 10 倍,還繞過拒絕 fallback 的守衛 | fail-closed:規格抓不到就中止/停止下單;移除 BTC/ETH 特例或改正 0.1 |
| C6 | **high** | positions.py:51,58,81 | 無啟動對帳、`_redis` 從未連線、`load_from_okx`/`load_snapshot` 零呼叫 → 重啟後帳本歸零、reduce-only 被跳過、倉位/權益數學失真 | 啟動時 `rest.get_positions()` + `load_from_okx`(帶各標的 ctVal);Redis 真接或刪死碼與文件宣稱 |
| C7 | **high** | market_data_handler.py:70,96,246 | `ping_interval=None` + 心跳不驗 pong + 無資料齡看門狗 → 半開連線靜默永掛,對 stale book 交易、權益凍結 | 記每 socket 最後訊息時間,>~35s 無訊息/pong 就關 socket 重連;加「資料過期即拒單」時間閘 |
| C8 | **high** | circuit_breaker.py:36,47; market_data_handler.py:72,102; engine.py:405 | CircuitBreaker 無 caller(REST breaker 永不觸發);WS breaker 在 public 靜默殺 task、在 private 被自家 except 吞掉;引擎無 task 監督 | 由 REST/MDH 呼叫 `record_*`;MDH task 加 done-callback → `on_circuit_trip`(硬停+告警);`engine.main` 監督背景 task,任一退出視為致命 |
| C9 | medium | positions.py:227 | `apply_cashflow` 零呼叫 → funding 結算never入帳(但旗艦策略就是 funding carry)→ PnL/回撤/日虧全少一條主要金流 | 訂閱 OKX private account/bills 或輪詢 bills,每次結算 `apply_cashflow(...,reason='funding')` 後 `dd_tracker.update` |
| C10 | high | portfolio_manager.py:53-54; execution_handler.py:49; engine.py:300 | mid 取自原始 `books` delta(`bids[0][0]` 可能是深層或剛移除價)→ 權益爆量/歸零誤觸停損;維護良好的 `OkxBook` 卻沒被用 | 三個 consumer 改用 `okx_book.py` 的 `mid()`(:122)/`best_bid()`(:108)/`best_ask()`(:115);加深層-only 更新的回歸測試 |
| C11 | medium | portfolio_manager.py:207, 290-323 | funding carry 對沖腿無 mid/風控擋下時**靜默跳過** → 裸方向曝險,無告警無 journal(已列 KNOWN_ISSUES);另 :314 現貨腿誤用永續價定價 | **完整設計見下方「C11 設計」節**(前置定價修補 + 四層方案 + 驗收條件) |
| C-x | low | run_demo.py:20; engine.py:501 | demo gate 是可被 `python -O` 移除的 assert;`python -m engine` 可直接跑 config 內的 live | 改 `if cfg.system.mode!='demo': sys.exit(...)`;`engine.main` 非 `allow_live=True` 拒 mode==live |

**額外(附帶但屬 correctness/安全鄰接):**
- C-vol `sizing.py:51`(medium):vol targeting 用 `sqrt(365*24)` 年化,但 `update_return` 只在成交時餵「成交間報酬」→ 波動估計依交易頻率失真、下單量錯一個 regime-dependent 倍數。改以固定時距(如 1m/1h close-to-close)取樣餵入。
- C-login `market_data_handler.py:257`(medium, KNOWN F29 鄰接):private WS 登入用原始本地時間簽章,忽略已同步的 clock offset;>30s 漂移即登入失敗且 F29 使 `run_private` 永久返回 → 私有成交/倉位更新全斷。把 REST clock offset 傳入 `_ws_login`。

### 建議執行順序 — 2026-08-03 修正版(取代原順序)

> **原順序 `C5 → C3 → C2 → C6 → C1 → C7 → C8` 已作廢。**
> Claude 覆核時發現兩個相依性缺陷,其中一個會讓系統比現狀更危險。
> 行號皆已對照 `6bdafa0` 重新驗證。

#### 缺陷一(嚴重):C1 必須排在 C10 之後

C1 要每 ~2 秒用 `positions.get_equity()` 餵 drawdown tracker;但在 C10 修好前,
mid 取自原始 WS delta([portfolio_manager.py:53-54](src/okx_quant/portfolio/portfolio_manager.py#L53-L54)),
`bids[0][0]` 可能是深層價或剛被移除的 `sz=0` 價位。先做 C1 等於**把一個會亂跳
的權益數字以 2 秒頻率接到硬停邏輯上** → 誤觸發硬停(停掉健康部位)或反向遮蔽
真實回撤。這比現狀(只在成交時更新)更糟:現狀是遲鈍,那個是會自己亂動手。

#### 缺陷二:C2 必須與 close_all 修補綁在一起

C2 會呼叫 [`broker.close_all()`](src/okx_quant/execution/broker.py#L153),但該函式
`instType="SWAP"` 寫死(:159)、`mgnMode="cross"` 寫死(:167)、整個迴圈包在單一
try 內(:170,一次例外就放棄剩餘部位)。雙腿 funding 帳本**持有現貨**,close_all
根本不會碰到現貨腿 → 做出一個「看起來有平倉、實際沒平乾淨」的硬停。假保證比
沒有保證更危險。

#### 四階段順序(每項一個 Change Manifest,逐項授權)

**Phase 1 — 先把輸入弄對(不新增任何自動動作)**

| 順序 | 項目 | 錨點(已驗證) |
| --- | --- | --- |
| 1 | C5 ctVal fail-closed | `engine.py:114`(live 預設)、`engine.py:124/126`(fallback);`portfolio_manager.py:134/274` 與 `_fallback_ct_val`(:345-350) |
| 2 | C10 改用維護中的訂單簿取 mid | `portfolio_manager.py:53-54`、`execution_handler.py:49`;改用 `okx_book.py` 的 `mid()`(:122)/`best_bid()`(:108)/`best_ask()`(:115) |
| 3 | C6 啟動對帳 | `positions.py:58` `load_from_okx`、:81 `load_snapshot`(皆零呼叫);`_redis` 於 :51 設 None 後從未被賦值 |
| 4 | **C11 Layer 1 pre-flight**(見下節) | `portfolio_manager.py:290-323` |

C11 的 Layer 1 刻意提前:它很小、純預防、且立刻關掉最大的裸露路徑。

**Phase 2 — 讓交易所真正執行程式已經假設的約束**

| 順序 | 項目 | 錨點 |
| --- | --- | --- |
| 5 | C3 送出 `reduceOnly` | `broker.py:88` 的 `place_order` kwargs |
| 6 | close_all 修補(C2 的前置) | `broker.py:153/159/167/170` |

**Phase 3 — 輸入與原語可信之後,才接上守衛**

| 順序 | 項目 | 錨點 |
| --- | --- | --- |
| 7 | C7 資料過期看門狗 + 過期拒單 | `market_data_handler.py:70/96`(`ping_interval=None`)、:246-252(`_heartbeat` 不驗 pong) |
| 8 | C1 mark-to-market 回撤 | `engine.py:339`(目前唯一的 `dd_tracker.update`) |
| 9 | C2 硬停撤單 + 平倉 | `engine.py:445-446`(只 cancel task,不撤單不平倉) |
| 10 | C8 breaker 接線 + task 監督 | `circuit_breaker.py:36/47`(**已再次確認零呼叫**);`market_data_handler.py:72`(在 try 外→靜默殺 task)與 :102(在 try 內→被自家 except 吞掉) |

**Phase 4 — 帳務完整性**

| 順序 | 項目 | 錨點 |
| --- | --- | --- |
| 11 | C4 孤兒單對帳 | `broker.py:135`(任何例外都回 None) |
| 12 | C9 funding 現金流入帳 | `positions.py:227` `apply_cashflow`(零呼叫) |
| 13 | C11 Layer 2-3 | 見下節 |

**保留自原順序:** C3 排在 C6 之前是對的——C3 讓交易所端強制 only-shrink,正好
在 C6 施工期間防住「本地帳本過期」這個風險。

**C5 是否該第一:** C5 只在 `get_instruments` 失敗時觸發(罕見但單次後果重:ETH
下單量 10 倍且 notional 低估 10 倍,連 fat-finger 上限都攔不住);C10 每個 tick 都
錯但在 C1 落地前 blast radius 較小。兩者互換可接受,不強制。

---

### C11 — funding cross-leg reconciliation 設計(回覆 Codex 提問)

#### 前置修補:現貨腿目前用永續價格掛單(新發現,必須先修)

[portfolio_manager.py:314](src/okx_quant/portfolio/portfolio_manager.py#L314):

```python
spot_price = self._resolve_price(spot_symbol, self._resolve_price(sig.inst_id))
```

而 `_resolve_price`(:104-107)是 **`preferred` 優先**:

```python
if preferred and preferred > 0:
    return preferred
return self._last_mids.get(inst_id, 0.0)
```

所以只要永續 mid 存在,現貨腿就用**永續的價格**掛單,`spot_symbol` 自己的 mid
完全不會被讀取。這不是「找不到時的 fallback」,是「有就優先用」。

這直接造成對沖腿失敗:正價差時永續價高於現貨,以永續價掛現貨**買單**會穿過
現貨價差 → `post_only` 被拒 → **對沖腿沒送出、主腿已成交 → 裸方向曝險**。
funding carry 的利潤只有幾 bps,腿價錯掉就吃光。

**修法:** 現貨腿改用現貨自己的 book 定價。**這必須先修**,否則下面 Layer 1 驗證
的是一個不是現貨真實價格的數字。

#### 目前的四條靜默失敗路徑

流程是**主腿先送、對沖腿後送**([:100-102](src/okx_quant/portfolio/portfolio_manager.py#L100-L102)),
且對沖腿有四條路徑靜默跳過,四種情況主腿**都已送出**,且無 log、無告警、無 journal:

| # | 觸發條件 | 位置 |
| --- | --- | --- |
| 1 | 對沖標的無 mid → `price <= 0` | `:207` 靜默 `return` |
| 2 | metadata 缺 `spot_symbol` | `:310-312` 靜默 `return` |
| 3 | 對沖腿自己的 RiskGuard 檢查擋下 | `:261` |
| 4 | 尺寸 `ROUND_DOWN` 後歸零 | `_compute_order_quantity`(`:277` 起) |

第五個結構性問題:**兩腿無關聯識別**,各自 `uuid4().hex[:32]`,事後無從查詢兄弟腿
狀態,重啟後無法重建配對。

#### 設計原則:不追求 atomicity,追求「有界、可偵測、可補償」

兩張分開的交易所訂單本質上無法原子化。目標改為:不對稱窗口是有界的、被偵測到
的、有明確補償動作。

**Layer 1 — Pre-flight 驗證(Phase 1 就做,價值/成本比最高)**

送出**任何一條腿之前**,先驗證所有腿都可送出:兩邊都有夠新的 mid(帶時效上限,
與 C7 共用)、尺寸格式化後皆非零、皆通過 RiskGuard、規格齊備。任一不過 →
**一張都不送**,記 ERROR + 發 RISK event。

這一層單獨關掉上表全部四條路徑。對 carry 策略而言「不交易」永遠是安全方向。

**Layer 2 — 腿的關聯識別**

同組腿共用 `group_id`,編進 clOrdId(OKX 允許 32 字元英數,例如
`g` + 16 hex group + 8 hex leg)並存進 OrderManager。沒有這層 Layer 3 做不出來,
重啟後也無法重建配對。

**Layer 3 — 成交後對帳與補償**

週期性檢查每個未平組:

- 兩腿都成交 → 平衡,結案
- 一腿成交、兄弟腿仍掛著 → 等到期限,逾時則撤兄弟腿並平掉已成交腿
- 一腿成交、兄弟腿被拒/不存在 → **補償平倉**,journal + 告警
- 兩腿部分成交且數量不等 → 把多的那腿削到相等

**政策明確採「拆解」而非「追價」。** funding carry 只有兩腿同時存在才賺得到錢;
追價完成配對等於把對沖套利變成進場時點的方向性賭注,那不是本策略的 edge。

**Layer 4 — 報表與告警**

每次補償動作寫 journal、critical 等級告警,並把「未配對腿事件次數」納入 shadow
報表作為**晉級 gate 指標**,而不只是 log。

**相依性:** Layer 3 跨重啟要有意義需要 C6;PnL 要誠實需要 C9。故 Layer 1
(+前置定價修補)排 Phase 1,Layer 2-3 排 Phase 4。

#### C11 驗收條件(binary)

- [ ] 現貨腿使用 `spot_symbol` 自己的 mid 定價;有測試證明永續 mid 存在時不再被優先採用
- [ ] 四條靜默路徑各有一個測試:對沖腿不可送出時**主腿也不送出**
- [ ] 任一腿被跳過時產生 ERROR log + RISK event(可被測試觀察)
- [ ] 同組兩腿共用可查詢的 `group_id`
- [ ] 單腿成交且兄弟腿失敗時,補償平倉被觸發並寫入 journal(整合測試)
- [ ] 未配對腿事件計數出現在 shadow 報表

---

### WS-C 通則(給 Codex)

- **不要整批授權、不要整批實作。** 逐項取得使用者授權,每項一個 Change Manifest
  (`docs/CHANGE_MANIFEST_TEMPLATE.md`)+ `python scripts/docs/check_doc_impact.py --strict`。
- Phase 3 的每一項都是「把自動動作接到風控上」。若輸入尚未修好就接線,失效方向
  是**會自己動手停掉交易或平掉部位**——所以 Phase 1→2→3 的順序不可跳。
- 每項需更新 `docs/FAILURE_MODES.md` / `docs/INVARIANTS.md` 並附守護測試。
- 修完**不得**宣稱 live/demo/shadow 就緒;仍受 `docs/ai_collaboration.md` gate 管。
- paper-demo 批次(`1992ac2`)已經改過 `broker.py`/`portfolio_manager.py`/
  `engine.py`,**不要重做**它已完成的部分:巢狀 `sCode` 驗證、`tag` 淨化、
  價格 tick 對齊(買 `ROUND_DOWN` / 賣 `ROUND_CEILING`)、SPOT `tdMode=cash`、
  private `orders` 頻道改 `ANY`。C4(逾時孤兒單)**仍未解決**。

---

## WS-D — 效能(資料管線/回測,非金流路徑,可安全並行)

### 診斷
攝取每次 flush 都把**整段 raw 歷史**重推 canonical(無 start/end)→ O(n²) DB 寫入;
parquet flush 每 60s 重讀重寫整日檔 → O(day²) I/O;多處 DataFrame 用 per-row dict /
`iterrows` 建構;API 每請求開新 asyncpg 連線;checkpoint 讀寫每次跑 DDL。

### Files to change
- `scripts/market_data/ingest.py`、`src/okx_quant/data/candle_store.py`、
  `src/okx_quant/data/feed_store.py`、`backtesting/replay.py`、
  `backtesting/data_loader.py`、`backtesting/artifacts.py`、`scripts/_db_writer.py`、
  `src/okx_quant/api/routes_data.py`、`src/okx_quant/api/routes_backtest.py`
### Files NOT to touch
- `src/okx_quant/strategies/`(除 D-ma 一項,屬 Codex ownership 但非本組必要)、
  已存在的 result artifacts(不得改)

| # | Sev | 檔案:行 | 問題 | 修法 | 預期增益 |
|---|-----|--------|------|------|---------|
| D1 | **high** | ingest.py:360; candle_store.py:885; canonical_policy.py:68 | 每 flush 無界重推全歷史 canonical;same-source 無 `IS DISTINCT FROM` 守衛 → 每列每次被實體改寫 | 傳 flush 視窗 min/max ts(±1 bar)給 `canonicalize_from_raw`;加 `ROW(...) IS DISTINCT FROM` 守衛 | 長回填 DB 寫入 ~100-1000× |
| D2 | high | feed_store.py:126 | parquet flush 每 60s 重讀重寫整日檔 | 每 flush 寫新 part 檔或用常駐 `ParquetWriter` 寫 row group | 日末 flush ~100× |
| D3 | medium | candle_store.py:537,864,1072; data_loader.py:955 | 千萬列查詢用 `[dict(r) for r in rows]` 建 DataFrame | 欄式建構 `pd.DataFrame(rows, columns=[...])` 或 `zip(*rows)` | 載入 ~10× |
| D5a | medium | replay.py:829-920 | 全事件先物化成 Event/MarketPayload 於單一 list 再排序(~5GB) | 各來源先排序 → generator + `heapq.merge` 惰性產生 | 峰值記憶體 ~N× |
| D5b | medium | replay.py:1368; 184-196 | recorder 每 market event 存 ~4 個 dict | 改欄式 scalar list/numpy;`record_book_snapshot` 加取樣旗標 | recorder 記憶體 ~5-10× |
| D4a | medium | _db_writer.py:93-131 | 下載入庫用 `iterrows` 逐列轉換 | 向量化驗證 + `itertuples` | 轉換 ~10-50× |
| D4b | medium | artifacts.py:1450 | 用 `iterrows` 掃全 price_df 只為取 unique inst_id | `price_df['inst_id'].unique()` | ~1000× |
| D7 | medium | candle_store.py:224-255 | checkpoint 讀寫每次跑 3×ALTER + CREATE(取 ACCESS EXCLUSIVE 鎖) | 首次成功後設 `_checkpoint_schema_ready` 旗標短路 | 每呼叫 ~4 round-trip + 去鎖 |
| D6 | low | routes_data.py(~15 處)、routes_backtest.py(4 處) | 每請求開新 asyncpg 連線(已列 KNOWN) | 啟動建 `app.state.pool`(min1/max10)逐請求 acquire | 每屏載入 ~50-100ms |
| D4c | low | routes_backtest.py:2049 | price-series fallback `iterrows` | 向量化 + `to_dict('records')` | 首屏 ~20-50× |
| D8 | low | feed_store.py:141-153 | timescale backend 每 (inst,table) flush 開新連線 + 逐列 INSERT | 常駐 pool + `copy_records_to_table` | flush ~5-10× |
| D-ma | low | technical_indicators.py:153 | MA crossover 每事件重算整段 rolling + 複製整個 deque | 維護 running sum 增量更新 | 每事件 ~100-1000× |

### Codex Task(D1+D2+D3+D7 一組;D4/D5 另一組)
```text
Task: 資料管線效能:界定 canonical 推送視窗、parquet append、欄式 DataFrame、快取 DDL
Plan source: tasks/2026-08-03-project-optimization-codex-plan.md §WS-D

PERMITTED FILES: 見上表 D1/D2/D3/D7 各檔 + tests/
FORBIDDEN: 既有 results/ artifacts、risk/portfolio/execution、config/risk.yaml
SCOPE LIMIT: 純效能重構,行為與輸出 byte 不變;不改 canonical 值語意(只加 IS DISTINCT FROM 守衛)。

REQUIRED ON COMPLETION:
- python -m pytest backtesting/ tests/unit -k "candle or ingest or feed or replay" -q
- python scripts/smoke/backtest_smoke.py   # 等同 make backtest-smoke
- 若 canonical 寫入語意有任何可觀察差異 → 這是商業規則變更,停下改走 Change Manifest 流程

ACCEPTANCE CRITERIA:
- [ ] canonicalize_from_raw 只掃 flush 視窗;同 source 相同列不再被 UPDATE(version 不動)
- [ ] 一段代表性回填的 canonical 結果與 main 逐列相同(附前後列數/hash 對照)
- [ ] parquet flush 不再重寫整日檔;讀取端結果不變
- [ ] 大查詢 DataFrame 欄式建構,dtype/欄序與既有一致(有測試)
- [ ] Diff 僅含 permitted 檔
```

---

## WS-E — 協作架構與可維護性

### 診斷
`AGENTS.md` 的驗證矩陣全是 make 目標,但本機無 make 且幾乎沒有等價指令文件;
`FEATURE_MAP`/`KNOWN_ISSUES`/`DATA_FLOW`/`RUNBOOK` 有多處與程式碼牴觸(locate-before-edit
權威失真);`AI_HANDOFF` 已 581 行且只限「每次新增 ≤15 行」保證單調膨脹;
`differential_validation.py` 8,162 行單體檔違反自家 300 行閱讀預算;`engine.main` ~420 行
組裝路徑無任何測試;binance spot/futures client 逐字重複 ~200 行。

### Files to change
- `docs/RUNBOOK.md`(+ 新增 `scripts/verify.ps1`)、`docs/FEATURE_MAP.md`、
  `docs/KNOWN_ISSUES.md`、`docs/DATA_FLOW.md`、`docs/AI_HANDOFF.md`、`Makefile`、
  `backtesting/differential_validation.py`(拆包)、`src/okx_quant/engine.py`(抽 builder)、
  `src/okx_quant/execution/binance_testnet/{spot,futures}_client.py`

| # | Sev | 檔案 | 問題 | 修法 |
|---|-----|------|------|------|
| E1 | **medium** | AGENTS.md:68; RUNBOOK | 驗證矩陣 make-only,本機無 make | 新增 `scripts/verify.ps1` + RUNBOOK「Windows without make」段,列每個 make 目標的 python/pytest/node 等價序列;矩陣引用之 |
| E2a | medium | FEATURE_MAP.md:858 | Binance testnet spot host / 憑證模型寫錯(兩個方向都錯) | 更正:spot `demo-api.binance.com`、futures `demo-fapi.binance.com`、unified key + 選擇性 `BINANCE_FUTURES_*` override;併入 2026-08-02 paper/demo 變更 |
| E2b | low | KNOWN_ISSUES.md:183 | 宣稱 `make verify` 缺 test-lab,但已 wired | 移到 Closed 或刪,保留「父/lab 需分開跑」 |
| E2c | low | DATA_FLOW.md:540 | 仍列 backtest-smoke fixture 為 missing gap(已閉) | 改為「跑 tiny frozen no-DB replay fixture(僅 smoke)」 |
| E2d | low | RUNBOOK.md:1683 | 稱前端為 React SPA + URL 路由(實為 Preact + state 路由) | 改寫為 Preact/htm、左欄 state 切換、WS `/api/ws?api_key=` |
| E3 | medium | AI_HANDOFF.md | 581 行,只限每次新增未限總量 | 加總量上限(如 ≤120 行)+ session-end 規則:早於當前里程碑者移入 CHANGELOG_AI/KNOWN_ISSUES |
| E4 | medium | differential_validation.py(8162)、routes_backtest.py(4068) | 單體巨檔違反 300 行閱讀預算 | 依既有接縫拆成 package + 相容 re-export;由既有 `test_differential_validation.py` 守護 |
| E5 | medium | engine.py:83 | `main()` ~420 行組裝無測試(此分支正在改 engine) | 抽 `build_engine(cfg)`(組裝不執行)+ demo/shadow 組裝測試(mock broker),斷言訂閱與關機順序 |
| E6 | low | binance spot vs futures client | ~200/270 行逐字重複 | 抽 `_SignedBinanceRestClient` base,子類只留 host/env/reduceOnly;由既有注入 transport 的測試守護 |
| E-git | low | (git 衛生) | `__pycache__/*.pyc` 追蹤狀況、result/log 大檔是否入庫 | 跑 `git ls-files` 對照 `.gitignore`;移除已追蹤的 `*.pyc`,補 gitignore(見下) |

### Codex Task(E1+E2 先做,低風險純文件/腳本)
```text
Task: 補 Windows 無-make 驗證腳本 + 修正 FEATURE_MAP/KNOWN_ISSUES/DATA_FLOW/RUNBOOK 文件漂移
Plan source: tasks/2026-08-03-project-optimization-codex-plan.md §WS-E

PERMITTED FILES: scripts/verify.ps1(新增)、docs/RUNBOOK.md、docs/FEATURE_MAP.md、
  docs/KNOWN_ISSUES.md、docs/DATA_FLOW.md、AGENTS.md(僅矩陣加註引用)
FORBIDDEN: 所有 src/、backtesting/、config/

REQUIRED ON COMPLETION:
- 跑 docs-check 等價序列(verify.ps1 內應含):
    python scripts/docs/check_doc_metadata.py
    python scripts/docs/check_feature_map_links.py
    python scripts/docs/check_ledger_consistency.py
- pwsh scripts/verify.ps1 -Target docs-check   # 自我驗證新腳本可跑

ACCEPTANCE CRITERIA:
- [ ] scripts/verify.ps1 覆蓋 docs-check/docs-impact/check-config/test-unit/test-lab/frontend-check/api-smoke/backtest-smoke/verify
- [ ] FEATURE_MAP Binance 段與 spot_client.py/futures_client.py 實際 host、憑證 fallback 一致
- [ ] KNOWN_ISSUES/DATA_FLOW 的已閉 gap 標為 Closed
- [ ] RUNBOOK 前端段描述與 frontend/app.js 一致
```

### 建議 `.gitignore` 補強(E-git,確認後再改)
```
__pycache__/
*.pyc
*.log
logs/
```

---

## WS-F — 第二輪補稽核(2026-08-03 gapfill,11/11 代理完成)

第二輪補掃了第一輪未涵蓋的五個面向 + 全庫完整性複查。結論:**git 歷史乾淨、
前端幾乎乾淨、無 notebooks、測試無真實連網**,但完整性複查抓到一條兩輪都漏掉的
**high**。

### F1 —(**high**,ungated,建議與 WS-A 一起做)Telegram 指令通道無寄件者驗證

- 檔案:[`telegram_alert.py:46-50`](src/okx_quant/monitoring/telegram_alert.py#L46)
- 事實(Claude 親自覆核):`command_loop` 只取 `msg["text"]` 就交給
  `_handle_command`,**從未**比對 `msg["chat"]["id"]` / `from.id` 與
  `self._chat_id`。任何找到這個 bot 的 Telegram 使用者都能下指令。
- 後果:`/kill` = 任意人可停掉全部交易(DoS);更糟的是 `/reset` →
  `risk_guard.reset()` 會把 `kill=False`、`soft_stop=False`,並將所有策略
  size multiplier 還原 1.0 —— **在一次合法的回撤硬停之後,未授權者可一鍵清空
  全部風控狀態並恢復滿倉下單能力**。`reset()` 的 docstring 明寫
  "Requires operator confirmation",但呼叫端沒有任何 operator 檢查(與 WS-C
  同一種病:安全機制存在、但守衛從未被接上)。
- 修法:在 `command_loop`/`_handle_command` 內 fail-closed 比對
  `str(msg.get("chat",{}).get("id")) == self._chat_id`(或明確 from-id allowlist),
  不符即丟棄;`/reset` 另加確認 token 以兌現 docstring 的 operator 承諾。
- **注意:`monitoring/` 不在受保護路徑清單內,此項不需額外授權即可實作。**
- Manifest:N(資安/安全修補,不改 PnL 公式)

### F2 —(medium)RateLimiter 全域鎖跨越 sleep,任一 bucket 飽和就序列化全部

- 檔案:[`rate_limiter.py:41`](src/okx_quant/execution/rate_limiter.py#L41)
- 模組 docstring 宣稱 per-instrument 60/2s、per-endpoint 40/2s 的**分桶隔離**,
  但持有單一全域 `asyncio.Lock` 跨越 `asyncio.sleep()`,任一桶被限流時所有桶一起
  卡住——正是它存在要平滑的 burst 情境下失效,拖慢完全沒接近上限的標的下單。
- 修法:鎖內只算等待時間,釋放後 sleep,醒來重取鎖並**重新檢查**計數(迴圈),
  或改 per-key 鎖 dict。醒來後不要無條件 append。
- ⚠️ 位於 `execution/`,**需授權**(併入 WS-C 一起申請)。Manifest:N

### F3 —(medium)`market_klines` 無壓縮、全庫無 retention policy

- 檔案:[`001_ohlcv_pipeline_v2.sql:439`](src/okx_quant/data/migrations/001_ohlcv_pipeline_v2.sql#L439)
- 系統最大的表(2020+ 全解析度 1m,~30 標的)建成 hypertable 但**沒有**
  `timescaledb.compress` 也沒有 `add_compression_policy`,而 `raw_candles`/
  `canonical_candles`/`venue_canonical_candles` 都有。全庫 `add_retention_policy`
  零命中,`funding_rates`、`market_funding_rates`、`external_observations` 亦未壓縮。
- 修法:補一支 migration 對 `market_klines` 開壓縮
  (`segmentby='instrument_id,bar'`, `orderby='ts DESC'`, 30 天後壓)並明確
  **寫下 retention 立場**(即使是「永久保留、30 天後壓縮」也要寫明,讓省略是刻意的)。
  OHLCV 壓縮率通常 ~90%。Manifest:N(不改資料值)

### F4 —(low)`ensure_market_data_schema()` 的自癒 DDL 與 migration 002 漂移

- 檔案:[`candle_store.py:318`](src/okx_quant/data/candle_store.py#L318)
- 內嵌的 `CREATE TABLE market_instruments` 缺 `canonical_inst_id`(該欄只存在於
  migration 002)。若 DB 已有該表但 002 未跑,`CREATE IF NOT EXISTS` 是 no-op,
  隨後 `register_market_instrument` 的 INSERT 會炸
  `column "canonical_inst_id" does not exist`。正式 `init_db` 會套 002 所以是潛伏性。
- 修法:刪掉重複的 CREATE 改全靠有序 migration,或在自癒路徑補
  `ALTER TABLE ... ADD COLUMN IF NOT EXISTS canonical_inst_id`。

### F5 —(low/info)SQL 識別字與字面值插值

- [`candle_store.py:563`](src/okx_quant/data/candle_store.py#L563):
  `prefer_exchanges` 以 f-string 拼成 `WHEN mi.exchange='{ex}'` 字面值(來源是
  CLI `--prefer`,operator 可控),任何含引號的 token 會破壞語句。改傳 `text[]`
  參數 + `array_position($n::text[], mi.exchange)`。
- [`candle_store.py:1375`](src/okx_quant/data/candle_store.py#L1375):`detect_gaps(table=...)`
  把 `table` 當識別字插值(asyncpg 無法參數化識別字)。六個呼叫端都用預設值,
  目前不可觸及;加白名單即可。

### F6 —(medium/low,已知)每週 worklog 排程任務的 harness 過寬

- 檔案:[`run_weekly_worklog_task.cmd:7`](scripts/worklog/run_weekly_worklog_task.cmd#L7)
- `claude.cmd -p --allowedTools "Bash,Read,Write,Edit,Glob,Grep"` —— `-p` 無人審核
  自動放行,裸 `Bash` 允許任意 shell;prompt 又餵入 `git log --all` 的 commit body
  與 `tasks/*handoff*.md`,最後 `git push origin HEAD`。文件宣稱「scope-limited to
  docs/worklogs/」但那只是 prompt 文字,**沒有任何 enforcement 層支撐**。
- 驗證者持平註記:此為單人 repo、只推自己的 GitHub,實際注入面薄;但 blast
  radius 最大(agent 同時握有 Bash + push)。
- 修法:把範圍搬進 harness——
  `--allowedTools "Bash(git log:*),Bash(git add:*),Bash(git commit:*),Bash(git push:*),Read,Write(docs/worklogs/**),Glob,Grep"`,
  拿掉 `Edit`,`git log` 去掉 `--all` 只讀當前分支。
- 附帶(low/info):`quant_weekly_worklog` 與 `quant_h014_shadow_daily` 是手動註冊、
  無 committed 註冊腳本,權限姿態無法從 repo 稽核;建議比照
  `register_okx_market_data_task.ps1`(唯一有 `-LogonType S4U`/`-RunLevel Limited`/
  無密碼並自我斷言的)補成腳本。RUNBOOK 多處 `schtasks /Create` 亦未明寫
  `/RL LIMITED`(預設已是 LIMITED,純一致性)。

### F7 —(low)手冊頁 `dangerouslySetInnerHTML` 未消毒(潛伏)

- 檔案:[`view-manual.js:64`](frontend/view-manual.js#L64)
- `marked@13` 預設放行原始 HTML(v5+ 已移除 sanitize 選項),經
  `dangerouslySetInnerHTML` 原樣寫入 DOM。`<img src=x onerror=>` / `<svg onload=>`
  可執行。**目前無不可信輸入路徑**(10 個章節皆 repo 內靜態檔,`/api/manual/{slug}`
  由 manifest 決定檔名故無路徑穿越,無後端寫入該目錄),故為潛伏而非可利用。
- 修法:本地打包 DOMPurify 後 `DOMPurify.sanitize(marked.parse(md))`,兌現程式碼裡
  已有的 ponytail TODO。

### F8 —(info)測試無網路隔離安全網

- `pyproject.toml:57` 只有 `asyncio_mode`/`testpaths`,未裝 `pytest-socket`,
  兩個 conftest 也沒有 autouse 阻擋 socket 的 fixture。現況**全部正確 mock**
  (54 檔 603 處 MockTransport/injected opener/monkeypatch),但這個不變式**無強制力**,
  未來一次回歸就可能真的打到交易所或洩漏環境憑證。
- 修法:加 `pytest-socket` + autouse `disable_socket()`(放行
  `tests/integration/` 用的 in-process `ASGITransport`),並註冊 `lab` marker
  讓「分開跑」變成明示規則。

### 第二輪確認為乾淨的部分(不需動作)

- **git 歷史零真實憑證**:`.env` 從未被追蹤(`.gitignore` 第 1 行);pickaxe 掃過
  OKX/Binance/Deribit key、`BEGIN RSA/OPENSSH/PRIVATE`、`xoxb-`/`AKIA`/`ghp_`、
  Telegram token regex、120 commit 高熵值掃描——命中全為佔位符
  (`your_api_key_here`)、env 插值、測試假值,或 Plotly div-id UUID。
  無追蹤的 `.pyc`/`__pycache__`/`.log`(故先前 E-git 的 gitignore 補強**非必要**,
  降為可選)。
- **無 notebooks**(全庫 `.ipynb` 零檔)。
- **測試不打網路/DB**:全部注入 MockTransport / 假 asyncpg / ASGITransport;
  `test_binance_testnet_client.py:87-88` 那組 key/secret 是 Binance 官方文件的
  HMAC 範例向量,非實憑證。
- **前端其餘部分安全**:charts.js 全 SVG 走 htm 子節點插值;所有 view-*.js 以
  `${...}` 插值渲染 WS/API JSON,無 innerHTML;無 `eval`/`new Function`/
  `document.write`;Progress 頁不渲染 markdown。
- **HTTP client 全有 timeout**(src 內 28 個建構點皆顯式設定)。
- **無不可信反序列化**:`pickle`/`joblib`/`marshal`/`dill`/`yaml.load(` 在 src 零命中。
- **Dockerfile 跑非 root** `trader`;prometheus 僅 localhost 抓取;無 grafana provisioning。

> 註:完整性複查也獨立重報了 API fail-open(= WS-A A1)。兩輪獨立命中同一條,
> 佐證其優先度。

---

## 驗證指令對照(Windows PowerShell,無 make)

| make 目標 | PowerShell/python 等價 |
|-----------|------------------------|
| test-unit | `python -m pytest tests/unit -q` |
| test-lab | `python -m pytest tests/lab -q`(與 unit 分開跑) |
| docs-check | 三支:`check_doc_metadata.py` / `check_feature_map_links.py` / `check_ledger_consistency.py` |
| docs-impact | `python scripts/docs/check_doc_impact.py --strict` |
| backtest-smoke | `python scripts/smoke/backtest_smoke.py` |
| check-config | `python scripts/check_config.py`(見 Makefile 對應行) |

(此表即 E1 要落到 `scripts/verify.ps1` 的內容;先照此手動跑。)
