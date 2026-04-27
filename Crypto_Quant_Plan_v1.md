# OKX 加密量化交易深度研究：從微結構理論到實盤架構

**核心結論**：在 OKX 以 $1k–$10k 小資金操作，**非主流微結構策略（OBI/OFI、VPIN、Avellaneda–Stoikov market making）與資金費率套利的組合**最符合理論嚴謹與經濟邏輯要求，但成敗取決於執行細節，而非策略新穎度。在 VIP0 費率結構下，**純 taker 的高頻策略在數學上幾乎不可能獲利**——round-trip 費率就吃掉 15–30 bp 的每筆邊際。因此建議以 **maker-only (`post_only`) 微結構策略 + delta-neutral funding carry** 為兩條主線，以 Nautilus Trader 做 tick-level 回測，並以 ¼-Kelly 與 HMM regime filter 做風控。本報告涵蓋六類策略的完整數學、OKX API v5 端點、回測框架比較、風控公式與可部署的 Python 事件驅動架構。

---

## 1. 策略研究：理論、信號、alpha decay

### 1.1 Order Book Imbalance（OBI / OFI / Microprice）

**最基本定義**（Level-1 OBI）：

$$\text{OBI}_t = \frac{Q^b_t - Q^a_t}{Q^b_t + Q^a_t} \in [-1, 1]$$

**加權中間價（Weighted Mid）**：$P^{\text{wmid}} = (Q^a P^b + Q^b P^a)/(Q^b+Q^a)$；買量大時 wmid 被拉向 ask，反映即將發生的 ask 消耗。

**Stoikov 微價格（Microprice, 2018, SSRN 2970694）**——結構上為鞅的短期估計：

$$P^{\text{micro}}_t = \lim_{n\to\infty} \mathbb{E}[M_{t+\tau_n} \mid \mathcal{F}_t]$$

以 $(M_t, I_t, S_t)$（中價、失衡比、tick-spread）為 Markov 狀態透過過渡矩陣 $Q, R$ 遞迴計算，通常 6 步收斂。實證上優於 mid 與 weighted-mid。

**Cont–Kukanov–Stoikov (2014) OFI**——CKS 證明 OFI（包含 cancel 與 add，不只是 trade）與價格變化是**線性關係**：$\Delta P_k = \beta_k \cdot \text{OFI}_k + \epsilon_k$，斜率 $\beta \propto 1/\text{depth}$。多層級版本 **MLOFI**（Xu-Gould-Howison 2018）與 **Deep OFI**（Kolm-Turiel-Westray 2021）把 10 層堆疊送入 LSTM/CNN，R² 顯著提升。

**理論基礎**：Glosten-Milgrom 1985 的逆選擇框架——imbalance 具資訊性因知情者會偏斜其訂單；Moallemi 2014 的 queue position 理論——FIFO 隊列位置具 option 價值，對 BTC 這類 large-tick 資產可達半 spread。

**Alpha decay（加密市場實證）**：
- **L1 OBI**：100 ms – 2 s half-life（BTC/ETH perp）
- **MLOFI（1–5 層）**：1–10 s
- **Deep-OFI / CNN**：30 s – 1 min
- R² 通常每 1–3 秒衰減 50%（Lucchese 等 2024）

**信號工程最佳實踐**：(1) EWMA 平滑 half-life 約 200 ms；(2) 多層指數衰減權重 $w_k = e^{-\alpha k}$，$\alpha \in [0.3, 1.0]$；(3) 依 spread 分桶校準（Stoikov 結果：OBI 資訊性依賴 spread）；(4) 與 trade-sign 失衡（VOI）串接使用。

```python
import numpy as np

def compute_obi_features(bids, asks, depth=5, alpha=0.5):
    pb, qb = bids[0]; pa, qa = asks[0]
    mid, spread = 0.5*(pb+pa), pa-pb
    obi_l1 = (qb - qa) / (qb + qa + 1e-12)
    wmid   = (qa*pb + qb*pa) / (qb + qa + 1e-12)   # weighted mid
    k = np.arange(depth); w = np.exp(-alpha*k)
    qb_k = np.array([bids[i][1] for i in range(depth)])
    qa_k = np.array([asks[i][1] for i in range(depth)])
    obi_multi = (w*(qb_k-qa_k)).sum() / (w*(qb_k+qa_k)).sum()
    I = qb/(qb+qa+1e-12)
    microprice = mid + (I - 0.5)*spread   # Stoikov first-order
    return dict(mid=mid, wmid=wmid, micro=microprice,
                obi_l1=obi_l1, obi_multi=obi_multi, spread=spread)

def compute_ofi(prev, curr):
    """Cont-Kukanov-Stoikov OFI increment between two L1 snapshots."""
    e_bid = (curr['pb']>=prev['pb'])*curr['qb'] - (curr['pb']<=prev['pb'])*prev['qb']
    e_ask = (curr['pa']<=prev['pa'])*curr['qa'] - (curr['pa']>=prev['pa'])*prev['qa']
    return e_bid - e_ask
```

**加密特有挑戰**：spoofing（過濾訂單年齡 < 100 ms 的層級）、碎片化（跨 Binance/Bybit/OKX/Coinbase 加權 microprice）、24/7（用 Guéant-Lehalle-Fernandez-Tapia 2013 的 ergodic 版本取代終端 T）。

### 1.2 VPIN / Flow Toxicity

**Easley–López de Prado–O'Hara (2012)** 的 VPIN 跳過 PIN 模型的 MLE，改在**成交量時鐘**上分桶：

$$\boxed{\text{VPIN} = \frac{\sum_{\tau=1}^{n} |V^S_\tau - V^B_\tau|}{n \cdot V}}$$

**Bulk Volume Classification (BVC)**——以正態 CDF 把成交量機率性地分配給買/賣：

$$V^B_i = V_i \cdot Z\!\left(\frac{\Delta P_i}{\sigma_{\Delta P}}\right),\quad V^S_i = V_i - V^B_i$$

**經濟直覺**：VPIN 上升代表單邊流持續消耗 MM 庫存；MM 擴大 spread 或撤單，形成 liquidity→volatility 回饋——ELO 記錄的 2010 Flash Crash 前兆機制。**關鍵警告**：Andersen-Bondarenko (2014) 批判其在 S&P e-mini 的預測力主要是機械性的同期相關；但 **Kitvanitphasu et al. (2025)** 發現 VPIN 在 BTC 經 VAR 確實顯著預測跳躍。

**Crypto 參數建議**（BTC-USDT perp）：
- 分桶大小 V ≈ 日成交量的 1/50 到 1/100（約每 15–30 分鐘填滿一桶）
- 支撐窗口 n = 50
- Time bar = 1 秒（Majors）或 100 ms（HFT）
- 門檻經驗法則：< 0.25 健康；0.45–0.55 警戒；> 0.70 極端毒性

**Krypton Labs 研究**：頂級 AMM 的平均毒性比 CEX 高 3.88 倍，LP 每 3 筆交易有 1 筆被逆選擇。

```python
import numpy as np, pandas as pd
from scipy.stats import norm

def compute_vpin(trades, V_bucket, n_window=50, bar_seconds=1):
    trades['ts'] = pd.to_datetime(trades['ts'])
    bars = (trades.set_index('ts').resample(f'{bar_seconds}s')
            .agg(close=('price','last'), volume=('size','sum')).dropna())
    bars['dp'] = bars['close'].diff()
    sigma = bars['dp'].rolling(1000, min_periods=50).std()
    bars['vB'] = bars['volume'] * norm.cdf(bars['dp']/sigma)
    bars['vS'] = bars['volume'] - bars['vB']
    bars['bucket'] = (bars['volume'].cumsum() // V_bucket).astype(int)
    bkt = bars.groupby('bucket').agg(vB=('vB','sum'), vS=('vS','sum'))
    bkt['imb'] = (bkt['vB'] - bkt['vS']).abs()
    bkt['VPIN'] = bkt['imb'].rolling(n_window).sum() / (n_window * V_bucket)
    bkt['CDF']  = bkt['VPIN'].rank(pct=True)   # 動態警戒水位
    return bkt
```

VPIN 是**無方向性**信號——作為 volatility regime switch 使用，需配合 CVD 或 OBI 取方向。

### 1.3 Avellaneda–Stoikov Market Making

**AS (2008)** HJB 封閉解；設中價 $dS = \sigma dW$、訂單到達強度 $\lambda(\delta) = A e^{-k\delta}$、CARA 效用、風險厭惡 $\gamma$、終端 $T$：

$$\boxed{r(s,q,t) = s - q\,\gamma\,\sigma^2(T-t)}\quad\text{（保留價）}$$

$$\boxed{\delta^a + \delta^b = \gamma\sigma^2(T-t) + \frac{2}{\gamma}\ln\!\left(1 + \frac{\gamma}{k}\right)}\quad\text{（最優總 spread）}$$

第一項是庫存成本，第二項是純逆選擇成本（書越密 $k$ 越大、spread 越窄）。Ho-Stoll (1981) 是其離散前身；Glosten-Milgrom (1985) 提供 Bayesian 逆選擇保費的微觀基礎。

**Crypto 改造**：
1. **24/7 → 無限期限**：用 GLFT 2013 的 ergodic limit，庫存懲罰變 $-q\gamma\sigma^2\eta$。
2. **資金費率**：保留價再減 $\mathbb{E}[f_t]\cdot\text{horizon}$；正 funding 時傾向累積空頭。
3. **Maker rebates**：淨 edge = $\delta - \text{fee}^{\text{maker}}$；負費率下 queue priority 壓倒 spread 寬度。
4. **Alpha 疊加**：fair value = microprice + $c_1\cdot\text{OFI}_t$，再套用 AS 庫存 skew。
5. **VPIN 動態擴 spread**：$\delta \to \delta \cdot (1 + \beta\cdot\text{VPIN})$，在高毒性區間自動後撤。

**典型參數（BTC-USDT perp）**：γ ∈ [0.01, 0.5]（alts 更高）；σ 用 5–10 分鐘 EWMA；k 每小時從 $Ae^{-k\delta}$ 回歸重校；max inventory 為 clip size 的 50 倍；$c_1$ ≈ 10–200 ticks；refresh 100 ms – 1 s。

```python
def as_quote(mid, inventory, alpha_signal, vpin,
             gamma=0.1, sigma=0.003, kappa=1.5, T_minus_t=1.0,
             tick=0.1, max_pos=50, c_alpha=100, beta_vpin=2.0):
    fair        = mid + c_alpha * alpha_signal
    reservation = fair - inventory * gamma * sigma**2 * T_minus_t
    spread_AS   = gamma*sigma**2*T_minus_t + (2/gamma)*np.log(1 + gamma/kappa)
    spread      = spread_AS * (1 + beta_vpin * max(vpin-0.4, 0))
    half = 0.5 * spread
    bid, ask = reservation - half, reservation + half
    if inventory >=  max_pos: bid = -np.inf
    if inventory <= -max_pos: ask =  np.inf
    return round(bid/tick)*tick, round(ask/tick)*tick
```

**統一經濟邏輯**：這三個策略全部是 information-asymmetry 的不同切面——OBI/OFI 讀取有方向的需求、VPIN 衡量該需求的毒性、AS 在給定這兩者下最優定價庫存+逆選擇成本。生產級 stack 會同時使用這三者。

### 1.4 Funding Rate Arbitrage（OKX 永續資金套利）

**OKX 資金費率公式**（2025 年 4 月遷移後）：

```
FundingRate = clamp[AvgPremium + clamp(InterestRate − AvgPremium, ±0.05%),
                   ±Cap]
InterestRate = 0.03% / (24/SettlementInterval)  # 0.01% 每 8h → 約 10.95% APR 基線
AvgPremium_Tn = Σ(i·P_i) / Σ(i)                  # 時間加權
```

結算每 8 小時（00:00, 08:00, 16:00 UTC）進行，部分合約 1/2/4h。

**Cash-and-carry delta-neutral**：多現貨 BTC + 空等值 BTC-USDT perp，收 funding。年化收益 $\text{APR} = \bar{r}_{8h} \times 1095$；0.01% → 10.95%，0.03% → 32.85%。

**VIP0 成本結構**：
| Leg | Maker | Taker |
|---|---|---|
| Spot | 0.080% | 0.100% |
| USDT-M Perp | 0.020% | 0.050% |

Round-trip 全 taker **0.30%**，maker-maker **0.20%**。30 日持有全 taker 的 break-even 年化 = 0.30%/(30/365) = **3.65% APR**；90 日 maker-maker 僅 **0.81% APR**。

**歷史數據**（CryptoQuant/Coinglass aggregates 2022–2025）：BTC/ETH perp funding 中位數約 0.01%/8h（≈ 10–11% APR）；牛市如 2023Q4、2024Q1 7D 平均 20–60%，峰值破 80–100%。FTX 事件、2024 八月日圓 carry unwind 出現反向視窗。

**$5k 範例**：$2,500 現貨 + $2,500 保證金撐 1× 短 perp；15% funding APR 年化收入 ≈ $375；月度 rebalance 費用 ≈ $15；淨收益 ≈ 7%。文獻 Sharpe **1.5–3**（calm）、**0.5–1**（含 liquidation-tail）。

**主要風險**：perp 端爆倉（rally 中短腿受傷）、basis blowout 退場、交易所風險（Makarov-Schoar JFE 2020 顯示跨所 spread 無法純以費率解釋）。

### 1.5 Basis Trading（現貨 vs 永續 / 季度）

**季度期貨 fair value**：$F_t = S_t \cdot e^{rT}$；$\text{AnnBasis} = (F/S - 1) \cdot 365/T$。OKX 季度 BTC/ETH 牛市時 5–15% 年化；熊市近 0 或負。**Perp fair value** 由 funding 無套利條件鎖定：$\mathbb{E}[\int r_{\text{funding}} dt] \approx (F_{\text{perp}}-S)/S$。

**均值回歸建模**：log-basis $b_t = \ln(F/S)$ 作 AR(1)：$b_t = \phi b_{t-1} + \epsilon_t$，半衰期 $\text{HL} = -\ln 2/\ln\phi$。季度期貨在到期收斂；perp 每 8h 被 funding clamp 拉回。進出場 z-score：z > +2 進場賣 perp 買現貨，z 穿越 0 平倉，|z| > 4 停損。BTC perp-vs-spot log-basis 典型 σ ≈ 3–8 bp/hour，HL 3–12 hours。

### 1.6 Pairs Trading（BTC-ETH 等）：協整與 OU

**Engle-Granger**：OLS $Y_t = \alpha + \beta X_t + u_t$，對 $\hat{u}_t$ 做 ADF 拒絕單位根 → 協整。**Johansen**：VECM 檢定 rank(Π)，支援多資產。

**OU 過程**：$dS_t = \theta(\mu - S_t)dt + \sigma dW_t$，離散 AR(1) 映射：$\theta = -b/\Delta t$，$\text{HL} = \ln 2/\theta$。

**動態 hedge ratio（Kalman）**：$\beta_t = \beta_{t-1} + w_t$，$Y_t = \beta_t X_t + v_t$；crypto regime 漂移嚴重（ETH/BTC beta 2022–2025 在 0.6–1.4 間擺動），Kalman 優於靜態 OLS。

進出場：|z| > 2 進、|z| < 0.3 平、|z| > 4 停損。Tadi-Kortchemski (arXiv 2109.10662) 顯示動態窗口 KSS+Johansen 在 Bitmex 跑贏靜態，但雙位數 drawdown 常見。BTC-ETH 小時級 Sharpe 0.5–1.5，basket 級可達 2.0（扣費前）。

```python
import numpy as np, pandas as pd, statsmodels.api as sm
from statsmodels.tsa.stattools import coint, adfuller

def estimate_ou(spread):
    lag = spread.shift(1).dropna(); dlt = spread.diff().dropna()
    X = sm.add_constant(lag); res = sm.OLS(dlt, X).fit()
    a, b = res.params
    theta = -b; mu = -a/b
    sigma = np.std(res.resid) * np.sqrt(-2*b/(1-np.exp(2*b)))
    return dict(theta=theta, mu=mu, sigma=sigma, half_life=np.log(2)/theta)

def pair_check(y, x):
    t, pval, _ = coint(y, x)
    beta = sm.OLS(y, sm.add_constant(x)).fit().params[1]
    spread = y - beta * x
    return pval, adfuller(spread, maxlag=1)[1], beta, estimate_ou(spread)
```

### 1.7 Realized vs Implied Vol（OKX Options）

OKX 上 BTC/ETH 歐式選擇權，每日/每週/每月/每季到期；費率 **0.02% maker / 0.03% taker**，capped 於 premium 的 12.5%。流動性為 Deribit 的 5–10%。

**RV 估計器**（annualize $A=365$）：CtC、**Parkinson** ($\sigma^2 = A/(4n\ln 2)\sum[\ln H/L]^2$)、**Garman-Klass**、Rogers-Satchell、**Yang-Zhang**（24/7 crypto 首選，drift/gap robust，效率 ~14×）。

**Variance Risk Premium**：$\text{VRP}_t = \text{IV}^2_t - \mathbb{E}[\text{RV}^2_{t,t+T}]$。Alexander-Imeraj (JAI 2020) 及後續 arXiv 2410.15195：BTC 30 日 VRP ≈ **+0.14 variance units**（相比 SPX ≈ 0.02）；IV > RV 約 70% 時間。

**Delta-hedged 做空 vol P&L**：$P\&L \approx \frac{1}{2}\int_0^T \Gamma_t S_t^2 (\sigma^2_{\text{IV}} - \sigma^2_{\text{RV},t})\,dt$——在 IV > RV 時正收益，ATM 短跨最大 gamma。

**$1k–$10k 可行性**：OKX 選擇權最小合約 0.01 BTC（≈ $700），一張 ATM straddle 權利金 ≈ $50，fee cap 對便宜 OTM 觸發。建議改做月度小幅 OTM strangle。文獻 Sharpe **1.0–2.0**，但 March 2020 / May 2021 / Nov 2022 都有 −20% 級別 drawdown。

---

## 2. OKX API v5 技術細節

### 2.1 REST 端點（Base: `https://www.okx.com`）

**Market Data**（公開）：
- 訂單簿 ≤400 層：`GET /api/v5/market/books?instId=BTC-USDT&sz=400`
- 完整訂單簿 5000 層：`GET /api/v5/market/books-full`
- K 線：`GET /api/v5/market/candles?instId=...&bar=1m&limit=300`（bar: `1s,1m,3m,5m,15m,30m,1H,2H,4H,6H,12H,1D,1W,1M`）
- 歷史 K 線：`GET /api/v5/market/history-candles`
- 最新交易：`GET /api/v5/market/trades`
- Funding：`GET /api/v5/public/funding-rate?instId=BTC-USDT-SWAP`；歷史：`/api/v5/public/funding-rate-history`
- 開倉量：`/api/v5/public/open-interest`；標記價：`/api/v5/public/mark-price`
- 合約資訊：`/api/v5/public/instruments`（含 `minSz`, `lotSz`, `tickSz`, `ctVal`）
- 倉位階層：`/api/v5/public/position-tiers`

**Trading**：`POST /api/v5/trade/order`、`/batch-orders`（≤20）、`/cancel-order`、`/amend-order`、`/order-algo`、`/close-position`、`GET /orders-pending`、`/orders-history`。

**Account**：`/api/v5/account/balance`、`/positions`、`/set-leverage`、`/set-position-mode`、`/trade-fee`、`/max-size`、`/bills`。

**認證（REST）**：四個 header——`OK-ACCESS-KEY`、`OK-ACCESS-SIGN = Base64(HMAC_SHA256(timestamp+METHOD+path+body, secret))`、`OK-ACCESS-TIMESTAMP`（ISO-8601 ms UTC）、`OK-ACCESS-PASSPHRASE`。時戳 > 30 秒不同步回 50102，需同步 `/api/v5/public/time`。

```python
import hmac, hashlib, base64, datetime as dt, json, requests
API_KEY, SECRET, PASS = "...", "...", "..."
BASE = "https://www.okx.com"

def _ts():
    return dt.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.') + \
           f"{dt.datetime.utcnow().microsecond//1000:03d}Z"

def _sign(ts, method, path, body=""):
    msg = f"{ts}{method}{path}{body}".encode()
    return base64.b64encode(hmac.new(SECRET.encode(), msg, hashlib.sha256).digest()).decode()

def request(method, path, params=None, body=None):
    from urllib.parse import urlencode
    body_str = json.dumps(body) if body else ""
    if params and method == "GET":
        path += "?" + urlencode(params)
    ts = _ts()
    headers = {"OK-ACCESS-KEY":API_KEY, "OK-ACCESS-SIGN":_sign(ts,method,path,body_str),
               "OK-ACCESS-TIMESTAMP":ts, "OK-ACCESS-PASSPHRASE":PASS,
               "Content-Type":"application/json",
               # "x-simulated-trading":"1"   # demo
              }
    return requests.request(method, BASE+path, headers=headers,
                            data=body_str if body else None).json()
```

### 2.2 WebSocket API

**端點**：
- Public：`wss://ws.okx.com:8443/ws/v5/public`
- Private：`wss://ws.okx.com:8443/ws/v5/private`
- Business（K 線、algo）：`wss://ws.okx.com:8443/ws/v5/business`
- Demo：改 host 為 `wspap.okx.com` 並附 `?brokerId=9999`

**關鍵頻道**：

| Channel | 深度 / 頻率 | 備註 |
|---|---|---|
| `bbo-tbt` | top-1, 10 ms | snapshot |
| `books5` | top-5, 100 ms | snapshot |
| `books` | 400 層, 100 ms | snapshot + 增量 + checksum |
| `books50-l2-tbt` | 50 層, 10 ms | VIP4+ 需登入 |
| `books-l2-tbt` | 400 層, 10 ms | VIP5+ 需登入 |
| `trades` / `trades-all` | 即時 | |
| `funding-rate`, `mark-price`, `open-interest`, `liquidation-orders` | | |
| `candle1m` 等 | **在 `/business`** | |

**訂閱**：`{"op":"subscribe","args":[{"channel":"books","instId":"BTC-USDT-SWAP"}]}`。**Heartbeat**：30 秒無訊息連線會斷，每 25 秒送字串 `"ping"`（非 JSON），伺服器回 `"pong"`。**Rate limits**：新連線 3/s per IP；sub/unsub/login 480/hour per 連線；訂閱 payload ≤ 64 KB。

**Orderbook 維護**：snapshot + incremental，含 `seqId`/`prevSeqId`——若 prevSeqId ≠ 本地最後 seqId 必須重訂閱。**Checksum**：對前 25 層 bid/ask 以 `"bidPx:bidSz:askPx:askSz:…"` 交錯串接（一側用完後接剩下的），CRC32 後轉 signed int32，必須等於 server 的 `checksum`。**關鍵**：保留伺服器回傳的原始價格字串，不要 reformat。

```python
import asyncio, json, zlib, websockets
from sortedcontainers import SortedDict

class OkxBook:
    def __init__(self, inst):
        self.inst, self.seq = inst, None
        self.bids, self.asks = SortedDict(), SortedDict()
    def _apply(self, side, levels):
        book = self.bids if side=="bids" else self.asks
        for px, sz, *_ in levels:
            p = float(px)
            book.pop(p, None) if float(sz)==0 else book.__setitem__(p, sz)
    @staticmethod
    def _signed(x): return x - (1<<32) if x >= (1<<31) else x
    def _checksum(self):
        bids = list(reversed(self.bids.items()))[:25]
        asks = list(self.asks.items())[:25]
        parts = []
        for i in range(max(len(bids), len(asks))):
            if i < len(bids): parts += [str(bids[i][0]), bids[i][1]]
            if i < len(asks): parts += [str(asks[i][0]), asks[i][1]]
        return self._signed(zlib.crc32(":".join(parts).encode()))
    def handle(self, msg):
        if msg.get("action") == "snapshot":
            self.bids.clear(); self.asks.clear()
        d = msg["data"][0]
        self._apply("bids", d["bids"]); self._apply("asks", d["asks"])
        if d.get("prevSeqId", -1) not in (-1, self.seq) and self.seq is not None:
            raise RuntimeError("seq gap -> resubscribe")
        self.seq = d["seqId"]
        if int(self._checksum()) != int(d["checksum"]):
            raise RuntimeError("checksum mismatch -> resubscribe")
```

### 2.3 費率結構（2026 年 4 月，重要）

**Spot（VIP 階層）**：

| Tier | 資格 | Maker | Taker |
|---|---|---|---|
| Lv1 | 預設 | 0.080% | 0.100% |
| Lv2–Lv5 | OKB 持有 | 0.075→0.070% | 0.090→0.080% |
| VIP1 | ≥$5M 量 或 ≥$100k 資產 | 0.045% | 0.050% |
| VIP3 | ≥$100M 量 | 0.030% | 0.040% |
| VIP5 | ≥$500M 量 | 0.010% | 0.030% |
| VIP8 | ≥$5B 量 | **-0.010%** | 0.015% |

**Perpetual**：Lv1 0.020%/0.050%；VIP1 0.015%/0.040%；VIP5 0.003%/0.022%；VIP8 **-0.005%**/0.015%。

**$1k–$10k 帳戶停留在 Lv1**。實務成本：Spot round-trip maker+taker ≈ 0.18%；Perp round-trip maker+taker ≈ 0.07%，全 taker 0.10%。**結論：必須以 `post_only` maker-only 策略為主**。持有 OKB 升至 Lv2 與開啟 settle-in-OKB 可微幅折價。以 `GET /api/v5/account/trade-fee` 實時核對。

### 2.4 訂單類型

`ordType`：`limit`、`market`、`post_only`（會 cross 則拒絕）、`fok`、`ioc`、`optimal_limit_ioc`（以 BBO IOC）、`mmp`、`mmp_and_post_only`。

**Algo** (`/api/v5/trade/order-algo`)：`conditional`（單邊 TP 或 SL）、`oco`、`trigger`、`move_order_stop`（trailing）、`iceberg`、`twap`、`chase`。

關鍵參數：`tdMode`（`cash`/`cross`/`isolated`/`spot_isolated`）、`posSide`（`long`/`short`/`net`）、`reduceOnly`、`clOrdId`、`expTime`、`tpTriggerPx`/`slTriggerPx`（附掛 TP/SL）。`slOrdPx="-1"` 代表觸發後市價執行。

### 2.5 Rate Limits 與 Position Limits

**REST**：公開約 20 req/2s per IP per endpoint（`books` 與 `candles` 約 40/2s）；下單 60 req/2s per instrument per sub-account（REST + WS 共用）；batch 300/2s。子帳戶總下單 1,000/2s。**低 fill-ratio 會降頻率配額**——對 scalping 不友善。

**Position Limits**：`/public/position-tiers` 給出分段表；BTC/ETH perp 最高 100–125×，主流 alts 50–75×，中小 alts 20–25×。**$1k–$10k 建議 3–5× 實際槓桿**——125× 存在但 tick noise 就會爆倉。

**最小交易單位**（至關重要）：
| Contract | ctVal | minSz | 最小名目 |
|---|---|---|---|
| BTC-USDT-SWAP | 0.01 BTC | 0.1 | ~$70 |
| ETH-USDT-SWAP | 0.1 ETH | 0.1 | ~$30 |
| BTC Options | 0.01 BTC | 1 | ~$700（$1k 帳戶過大） |

**架構建議**：(1) 盡量用 WS，不要 poll REST；(2) 批次下單/撤單（≤20）；(3) 分離 market data 與 trading 連線；(4) 以 `/private` WS 的 order/batch-orders op 下單比 REST 更快；(5) 每策略一組 API key（獨立 rate-limit bucket）。

### 2.6 Python SDK 選擇

| SDK | 優點 | 缺點 |
|---|---|---|
| **python-okx**（官方 wrapper） | 覆蓋 REST+WS，demo flag，`pip install python-okx` | 偏薄，async 回呼簡陋 |
| okx-sdk（Burakoner） | 結構現代化 | 社群維護，edge endpoint 需驗證 |
| **ccxt / ccxt pro** | 跨所統一，適合多交易所機器人 | 隱藏 OKX 特性（tdMode、posSide、algo 透過 `params` 易碎） |
| **cryptofeed** | 多所資料擷取 + 自動 book 維護 + checksum | 純資料，不下單 |
| **custom(websockets+requests)** | 完全可控，易審計 | 自行處理重連、checksum、rate limit |

**建議組合**：資料用 `websockets` + 自寫 checksum 或 `cryptofeed`；下單用 `python-okx` REST + 原生 `websockets` 接 private channel。API key **不要開啟 Withdraw 權限**，綁定靜態 IP。

---

## 3. 回測框架：tick-level 正確性與過擬合防禦

### 3.1 框架比較

| 框架 | 速度 | Tick / L2 | Live parity | 難度 | Crypto 適配 |
|---|---|---|---|---|---|
| **Backtrader** | 慢（~10k bars/s） | Bar | 弱 | 易 | CCXT，無 L2 |
| **VectorBT Pro** | 極快（vectorized） | Bar + limit | 無 | 中 | 好（自備資料） |
| **Nautilus Trader** | ~5M rows/s | **L1/L2/L3 原生** | **優**（同碼） | 難 | 優（Binance/Bybit/OKX adapter） |
| **Zipline-Reloaded** | 中低 | Minute | 弱 | 中 | 差 |
| **Hummingbot** | 中 | Bar + live LOB | 強（live） | 中 | 強（做市） |
| **QuantConnect/Lean** | 高（C#） | Tick（部分） | 強（鎖定雲端） | 中 | 尚可 |

**Backtrader** 2018 後停滯；單執行緒 Python bar loop 對百萬 tick 痛苦。**VectorBT** 向量化語意難以表達 queue/cancel 等路徑依賴邏輯。**Nautilus Trader** 以 Rust core + Python API，`OrderBookDelta`/`OrderBookDepth10` 原生支援，模擬撮合引擎支援 price-time priority、post-only、reduce-only、OCO/OTO；L2/L3 資料下 slippage 由**實際 book levels walking** 模擬；L1 下用 `FillModel(prob_slippage)`。**關鍵優勢：回測與實盤同一份策略程式碼**。

### 3.2 Tick vs Bar 回測

**Bar-level 遺漏**：bar 內成交、spread、queue position、微結構信號本身。任何持倉時間與 bar 等級相當的策略，bar 回測都是小說。**Tick 資料量**：BTCUSDT Binance L2 delta 每日 1–5 GB；儲存用 Parquet（Nautilus catalog 原生）、ArcticDB、或 ClickHouse。**Crypto tick 來源**：
- **Tardis.dev**——業界標準，50+ 所含 OKX Spot/Swap/Futures/Options，`books-l2-tbt`（每 10 ms）自 2019-12-03 起；每月 1 號免費樣本。
- **OKX 官方**——免費：trades 自 2021-09、OHLC 自 2023-07、funding 自 2022-03、L2 自 **2023-03**。
- Kaiko（貴）、CoinAPI、Amberdata。

**$1k–$10k 起點**：OKX 官方 L2 + Tardis 免費樣本，跑通後再升級 Tardis 付費（$200–500/月）。

### 3.3 Orderbook 回測正確性

**Look-ahead bias**：在 event-time 模擬下（Nautilus 模式），撮合引擎在推送事件給策略前已更新 book，你無法先看到自己的 fill。非規律 tick 上 `.shift(1)` 不夠，要用 `as-of join` 減掉決策延遲。

**Slippage 模型**（由粗到精）：
1. 固定 bps 或 spread 比例（小時級策略夠用）
2. **Volume-based book walk**：market order size Q 從頂部逐層吃，VWAP 為有效成交價——Nautilus 在 L2/L3 原生支援
3. **Square-root impact**：$\Delta P/P \approx \alpha \sigma \sqrt{Q/\text{ADV}}$，$\alpha \in [0.1, 1.0]$——適用於父單 >1% ADV
4. **Almgren-Chriss** 最優執行軌跡

**Queue position 模擬**（最難）：
1. 訂單抵達價格 $p$ 時記錄 $Q_{\text{ahead}}$
2. 每筆 $p$ 上的成交減去成交量，歸零後開始成交
3. $p$ 上的 cancel 按比例減少（假設均勻分布；無 L3 下為 best effort）
4. 若 book 穿越 $p$，全額成交於 $p$

**費用**：每 fill 扣費，perp 每 8h 計 funding：$P\&L_{\text{funding}} = \text{notional} \times r \times \text{sign(side)}$。**延遲**：outbound 10–50 ms、inbound 5–30 ms；忽略延遲的微結構策略 paper Sharpe 通常虛高 2–5×。

### 3.4 績效指標（公式 + 年化）

Crypto 年化用 **√365**（24/7）；小時資料 $\sqrt{365 \cdot 24}$。

```python
import numpy as np, pandas as pd
from scipy.stats import norm, skew, kurtosis

def sharpe(r, rf=0.0, periods=365):
    e = r - rf; return np.sqrt(periods) * e.mean() / e.std(ddof=1)

def sortino(r, rf=0.0, periods=365):
    e = r - rf; dn = e[e < 0]
    return np.sqrt(periods) * e.mean() / np.sqrt((dn**2).mean())

def max_drawdown(r):
    eq = (1 + r).cumprod(); return ((eq - eq.cummax())/eq.cummax()).min()

def calmar(r, periods=365):
    eq = (1 + r).cumprod(); years = len(r)/periods
    cagr = eq.iloc[-1]**(1/years) - 1
    return cagr / abs(max_drawdown(r))

def profit_factor(r): return r[r>0].sum() / abs(r[r<0].sum())
def win_rate(r):      return (r>0).sum() / (r!=0).sum()
def omega(r, tau=0):  return (r-tau).clip(lower=0).sum() / (tau-r).clip(lower=0).sum()
def tail_ratio(r):    return abs(np.percentile(r,95)) / abs(np.percentile(r,5))
```

### 3.5 Walk-Forward 與 CPCV

**Rolling walk-forward**：IS = 30–60 日、OOS = 7–14 日、step = OOS，適合 regime 漂移的 crypto。**CPCV**（López de Prado, AFML）：將樣本切 $N$ 組，取所有 $C(N,k)$ 個 test 組合，訓練集做 **purging**（移除 label 視界與 test 重疊的樣本）與 **embargo**（test 後加 h% 隔離區）。$N=6, k=2$ 得 15 組合、5 條完整路徑。Arian et al. (2024) 證明 CPCV 在 PBO 與 DSR 上全面優於 walk-forward。

### 3.6 過擬合檢測

**Deflated Sharpe Ratio（Bailey–LdP 2014）**——修正多次試驗與非常態偏度峰度偏誤：

$$\text{DSR} = \Phi\!\left(\frac{(\hat{\text{SR}} - \text{SR}_0)\sqrt{T-1}}{\sqrt{1 - \gamma_3 \hat{\text{SR}} + (\gamma_4-1)/4 \cdot \hat{\text{SR}}^2}}\right)$$

$$\text{SR}_0 = \sqrt{V[\text{SR}]}\cdot\left[(1-\gamma)\Phi^{-1}(1-1/N) + \gamma\Phi^{-1}(1-1/(Ne))\right]$$

$\gamma \approx 0.5772$ 為 Euler-Mascheroni，$N$ 為試驗數。DSR < 0.95 → 無法與運氣區分。

```python
def deflated_sharpe(returns, sr, sr_list, N):
    r = np.asarray(returns); r = r[~np.isnan(r)]
    T = len(r); g3, g4 = skew(r), kurtosis(r, fisher=False)
    var_sr = np.var(sr_list, ddof=1); euler = 0.5772156649
    SR0 = np.sqrt(var_sr) * ((1-euler)*1/norm.ppf(1-1/N)
                             + euler*norm.ppf(1-1/(N*np.e)))
    denom = np.sqrt(1 - g3*sr + (g4-1)/4*sr**2)
    return norm.cdf((sr - SR0) * np.sqrt(T-1) / denom)
```

**PBO（Probability of Backtest Overfitting）**：把 per-trial per-period return 矩陣對半切，依 IS Sharpe 排名，記錄 IS 贏家在 OOS 的排名。PBO > 0.5 代表選擇程序劣於隨機。

### 3.7 最終建議

**主框架：Nautilus Trader**——L2/L3 原生、OKX adapter、`OrderBookImbalance` 範例、nanosecond 時鐘、回測/實盤同碼、Parquet catalog 支援大於記憶體。**研究層**：先用 VectorBT 掃 1m/5m bar 的參數空間（秒級完成數千組合），選出 top 20 再到 Nautilus 跑 L2 高保真驗證。**流程**：vectorized 掃參 → Nautilus L2 IS/OOS → CPCV (N=6, k=2, 2% embargo) → DSR ≥ 0.95 → OKX demo paper 2 週 → 半 size 上線。

---

## 4. 風險管理：$1k–$10k 的小資金實務

### 4.1 Kelly 與分數 Kelly

**連續版 Kelly**：$f^* = \mu / \sigma^2$（在 perp 上是**槓桿**）。**Full Kelly 危險性**：μ 估計高 10% → Kelly bet 雙倍；drawdown to x 的機率約為 x（20% DD 機率 ≈ 20%）。**¼ Kelly**：保留 ~44% 幾何成長但 ~75% 減少變異；80% drawdown 機率從 1/5 降至 1/213（Yoder 分析）。

**建議**：¼ Kelly clamp 在 [0.25%, 2%] 每筆風險。Fixed-fractional 2% 回測常見 +95% return / −24.6% DD；5% 回測 +239% / −61.5% DD——生存性壓倒期望值。

**Volatility targeting**（最有效的單一風控）：$\text{notional}_t = (\text{target\_vol} / \text{realized\_vol}_t) \times \text{equity}$，自動在崩跌中去槓桿：

```python
def vol_target_size(returns, equity, target_ann_vol=0.20, lookback=30):
    realized = returns.rolling(lookback).std().iloc[-1] * np.sqrt(365*24)
    return equity * target_ann_vol / max(realized, 1e-8)
```

**ATR 停損 + 倉位**：2×ATR 停損覆蓋約 95% 正常波動。

### 4.2 多策略配置與相關性

**Crypto 的主導因子**：BTC beta、funding regime、跨所 basis、vol level——5 條「不同」策略常只有 ~1.5 個獨立賭注。分散收益公式：等權 $n$ 策略、平均相關 $\rho$ → $\sigma_{\text{port}} = \sigma\sqrt{(1+(n-1)\rho)/n}$。$\rho=0.3, n=4$ → 37% vol 減少；$\rho=0.7$ 僅 11%。

**HRP（Hierarchical Risk Parity, López de Prado 2016）**——避開 MV 的不穩定矩陣求逆：(1) 距離 $d_{ij}=\sqrt{0.5(1-\rho_{ij})}$；(2) 階層聚類 + 準對角化；(3) 遞迴二分依 cluster 變異倒數分配。

```python
from pypfopt import HRPOpt
hrp = HRPOpt(returns=strategy_returns_df)
weights = hrp.optimize()
```

**實務策略數上限**：
| Equity | 策略數 | 每策略資本 |
|---|---|---|
| $1,000 | 1 | $1,000 |
| $3,000 | 1–2 | $1,500 |
| $10,000 | 3–4 | $2,500 |

再多會撞上 OKX minNotional 與 fee drag 吃掉 alpha。

### 4.3 何時自動停止

**Drawdown halt**：軟停 10%（倉位對半）、硬停 15–20%（清倉 48h 冷卻）；日虧損 5% 全停。

**Regime detection**：
- **HMM 3-state**（`hmmlearn.GaussianHMM`，特徵用 return + 20-day range）識別 bull/bear/chop；trend 策略只在 bull state 全尺寸
- **CUSUM** 變點、`ruptures` PELT、**Bayesian online change-point**
- **GARCH**：條件 σ > 6 個月中位數 × 1.5 → 高波動 regime
- **相關性崩潰**：策略間 20 日 rolling 平均相關從 0.2 跳到 >0.6 → 總 gross 減半

**Strategy decay 偵測**：
- **Rolling IC**（Spearman(signal, fwd_ret), 60 trades）下降超 2 SE → 警戒
- **Bayesian α 更新**：$P(\alpha > 0) < 0.7$ → 減 size；< 0.5 → 退役
- **KS test**：live return 分布 vs backtest，p < 0.01（≥50 trades）

### 4.4 PSR（Probabilistic Sharpe Ratio）

$$\text{PSR}(\text{SR}^*) = \Phi\!\left(\frac{(\hat{\text{SR}} - \text{SR}^*)\sqrt{n-1}}{\sqrt{1 - \gamma_3\hat{\text{SR}} + (\gamma_4-1)/4 \cdot \hat{\text{SR}}^2}}\right)$$

PSR(0) < 0.95 → live track record 與 0 無統計差異；與 DSR 合用處理多試驗選擇偏誤。

```python
def psr(returns, sr_benchmark=0.0):
    r = np.asarray(returns); sr = r.mean() / r.std(ddof=1)
    g3 = ((r-r.mean())**3).mean() / r.std(ddof=1)**3
    g4 = ((r-r.mean())**4).mean() / r.std(ddof=1)**4
    num = (sr - sr_benchmark) * np.sqrt(len(r)-1)
    den = np.sqrt(1 - g3*sr + (g4-1)/4*sr**2)
    return norm.cdf(num / den)
```

---

## 5. 實際執行架構：事件驅動 Python 系統

### 5.1 標準事件流

```
MarketDataHandler ─(MarketEvent)─► SignalGenerator
                                       │
                                   (SignalEvent)
                                       ▼
                                 PortfolioManager ─(OrderEvent)─┐
                                       ▲                         ▼
                                   (FillEvent)              ExecutionHandler
                                       └─────────────────────────┘
```

解耦組件經過型別事件（async queue）溝通，回測與 live 共用控制流。

### 5.2 Asyncio 骨架

```python
import asyncio, json, logging, time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

class EvtType(Enum):
    MARKET=1; SIGNAL=2; ORDER=3; FILL=4

@dataclass
class Event:
    type: EvtType
    ts: float = field(default_factory=time.time)
    payload: Any = None

class MarketDataHandler:
    def __init__(self, bus, symbols): self.bus, self.symbols = bus, symbols
    async def run(self):
        import websockets
        url = "wss://ws.okx.com:8443/ws/v5/public"
        sub = {"op":"subscribe",
               "args":[{"channel":"tickers","instId":s} for s in self.symbols]}
        async for ws in websockets.connect(url, ping_interval=20):
            try:
                await ws.send(json.dumps(sub))
                async for msg in ws:
                    d = json.loads(msg)
                    if "data" in d:
                        await self.bus.put(Event(EvtType.MARKET, payload=d["data"][0]))
            except Exception as e:
                logging.warning(f"ws reconnect: {e}"); await asyncio.sleep(1)

class SignalGenerator:
    def __init__(self, out): self.out = out
    async def on_market(self, evt):
        # 插入策略邏輯（OBI、VPIN、basis z-score 等）
        sig = {"symbol": evt.payload["instId"], "side": "buy", "strength": 0.5}
        await self.out.put(Event(EvtType.SIGNAL, payload=sig))

class PortfolioManager:
    def __init__(self, out, risk): self.out, self.risk = out, risk
    async def on_signal(self, evt):
        size = self.risk.size(evt.payload)
        if size <= 0: return
        order = {**evt.payload, "size": size, "type":"post_only"}
        if self.risk.check(order):
            await self.out.put(Event(EvtType.ORDER, payload=order))

class ExecutionHandler:
    def __init__(self, out, broker): self.out, self.broker = out, broker
    async def on_order(self, evt):
        fill = await self.broker.submit(evt.payload)
        await self.out.put(Event(EvtType.FILL, payload=fill))

async def event_loop(bus, md, sg, pm, eh):
    asyncio.create_task(md.run())
    while True:
        evt = await bus.get()
        if   evt.type is EvtType.MARKET: await sg.on_market(evt)
        elif evt.type is EvtType.SIGNAL: await pm.on_signal(evt)
        elif evt.type is EvtType.ORDER:  await eh.on_order(evt)
        elif evt.type is EvtType.FILL:   pm.on_fill(evt)
```

### 5.3 基礎設施棧

| 層 | 建議 | 理由 |
|---|---|---|
| Tick 儲存 | **TimescaleDB** / InfluxDB | 壓縮 + 連續聚合 |
| 狀態 cache | **Redis** | 子毫秒讀取倉位/風控 |
| 交易台賬 | **Postgres** | ACID 審計 |
| 部署 | **Docker Compose + restart=always** | 可重現 |
| 監控 | **Prometheus + Grafana** | orders_sent, fills, api_errors, ws_reconnects |
| 告警 | **Telegram bot** / Discord webhook | halt、DD、latency spike |
| 日誌 | **structlog** JSON → Loki/ELK | 可查詢 |

**OKX co-location**：主撮合引擎在 Alibaba Cloud cn-hongkong；**AWS `ap-east-1`（HK）1–3 ms RTT 最佳**，Tokyo/Singapore 40–60 ms 可接受。Retail t3.small ~$15/月。

### 5.4 回測→實盤一致性

**Broker 抽象**——同一策略碼切換 SimBroker / OKXBroker：

```python
from abc import ABC, abstractmethod
class Broker(ABC):
    @abstractmethod
    async def submit(self, order): ...

class OKXBroker(Broker):
    def __init__(self, key, secret, pw, demo=True):
        from okx import Trade
        self.api = Trade.TradeAPI(key, secret, pw, flag="1" if demo else "0")
    async def submit(self, o):
        return self.api.place_order(
            instId=o["symbol"], tdMode="cross",
            side=o["side"], ordType=o["type"], sz=str(o["size"]))
```

**OKX Demo Trading**：Web → Demo Trading → 建立 Demo V5 API key；REST 加 `x-simulated-trading: 1`；WS 用 `wspap.okx.com?brokerId=9999`；`python-okx` 傳 `flag="1"`。

**Shadow trading（上線前 2–4 週）**：同時路由到 SimBroker + OKXBroker(demo=True)，比對 realized vs modeled slippage、fill rate、signal→ack latency、Σ(sim_pnl − demo_pnl) 漂移。

### 5.5 生產級硬編碼風控

```python
class RiskManager:
    def __init__(self, equity_fn):
        self.equity = equity_fn
        self.MAX_POS_USD        = 0.30    # 單品項 30% equity
        self.MAX_LEVERAGE       = 3.0
        self.MAX_DAILY_LOSS_PCT = 0.05
        self.MAX_ORDER_NOTIONAL = 500     # 防 fat-finger
        self.daily_pnl, self.kill = 0.0, False

    def check(self, o) -> bool:
        if self.kill: return False
        eq = self.equity(); n = o["size"] * o["price"]
        if n > self.MAX_ORDER_NOTIONAL: return False
        if n > self.MAX_POS_USD * eq:   return False
        if self.daily_pnl < -self.MAX_DAILY_LOSS_PCT * eq:
            self.kill = True; return False
        return True
```

**斷路器**：WS 60 秒重連 >3 次 / REST 錯誤率 >5% → 清倉停止；**Telegram `/kill` 指令**觸發 `close-position` 全倉；**冪等 clOrdId**（UUID）防重送；**stale quote 檢測**：訂單價偏離最後 tick >2% 拒絕。

### 5.6 策略退場決策框架

| 信號 | 行動 |
|---|---|
| Live Sharpe 在 backtest ±1σ，PSR(0) > 0.9 | **全 size** |
| Live Sharpe 低 1–2σ，rolling IC 跌 30% | **半 size** |
| Live Sharpe 低 ≥2σ，IC 失去顯著性，DD > 10% | **暫停** |
| 暫停 30+ 日重測無起色 | **退役** |

---

## 6. 具體執行 playbook（$1k–$10k 的 10 條鐵律）

**核心觀點收斂**：在 VIP0 費率下，純 taker 策略數學上難以獲利；**maker-only 微結構 + delta-neutral funding carry** 是 Sharpe 最能撐住的主軸。所有建議都以此結論為前提。

1. **Demo 先跑 ≥4 週**（`x-simulated-trading: 1`、`flag="1"`），確認事件迴路、checksum、重連、clOrdId 冪等全部穩定。
2. **策略主軸組合**：OBI/OFI 微結構 maker-only + AS market making（BTC/ETH perp）+ funding carry（delta-neutral）+ BTC-ETH Kalman pairs。放棄純 taker 的 triangular。
3. **倉位**：fixed-fractional 1% 風險為主；¼ Kelly 為上限；vol-target 20% annualized 覆蓋整體簿。
4. **策略數**：$1k 單策略；$10k 最多 3–4 策略；每週以 `PyPortfolioOpt.HRPOpt` 重配權重。
5. **風控閾值**：軟停 DD 10%、硬停 15%、日虧損 5%；HMM 3-state filter 只在 bull 跑 trend、reduce 在 high-vol。
6. **部署**：AWS `ap-east-1`（HK）t3.small，~$15/月，單進程 asyncio 事件迴路；超過 3 策略再考慮 Redis。
7. **資料**：OKX 官方 L2（自 2023-03）+ Tardis 免費樣本起步；驗證有 edge 再升級 Tardis 付費（$200–500/月）。
8. **回測協議**：VectorBT 掃參 → Nautilus L2 IS(30d)/OOS(7d) rolling walk-forward → CPCV (N=6, k=2, 2% embargo) → DSR ≥ 0.95 要求。
9. **上線分三階段**：Demo 4 週 → Shadow（live data + sim fill + demo fill 平行）2 週 → 半 size live，PSR(0) > 0.9 持續 2 週才升至全 size。
10. **硬編碼 guardrails** 放在策略程式碼無法 bypass 的獨立模組；結構化 JSON log；Grafana dashboard 必含 equity、drawdown、P50/P99 latency、WS reconnect rate、rolling Sharpe。

---

## 結語：理論嚴謹性與小資金現實的交集

這份研究最反直覺的發現是：**策略選擇其實次於結構選擇**。三種最紮實的微結構策略（OBI/OFI、VPIN、AS market making）共享同一個 Glosten-Milgrom 逆選擇核心，在 OKX VIP0 費率下只有 maker-only 執行在數學上可行；而數學上「簡單」的 funding carry 反而因 delta-neutral 特性在小資金可達 Sharpe 1.5–3，遠勝許多「酷炫」的機器學習策略在扣費後的真實表現。

**三項常被忽略的關鍵細節**：(1) 在 24/7 市場上 AS 的 $T-t$ 要換成 GLFT ergodic limit 否則公式發散；(2) VPIN 是**無方向**信號必須配 OBI/CVD 取向；(3) OKX 的 WS checksum 要用伺服器原始價格字串而非 reformat 後的字串，是最多人踩的坑。

**最該投入時間的地方**：不是尋找新 alpha，而是把 Nautilus + CPCV + DSR + PSR 這套**過擬合防禦**做紮實——在 $1k–$10k 尺度上，一個被 backtest 過擬合騙過的策略足以炸掉整個帳戶。López de Prado 的 AFML 在這個尺度上的價值超過任何單一策略教科書。

**對這位交易者的最終建議**：主線跑 **funding carry delta-neutral + OBI-aware maker-only AS MM on BTC-USDT-SWAP**，兩者相關性低；輔線上 **BTC-ETH Kalman pairs**。全部放在 AWS HK 單進程 Nautilus 架構上，8 週內完成 demo→shadow→half-size→full-size 的昇級路徑。真正的 edge 不在策略本身，而在執行紀律與過擬合控制。