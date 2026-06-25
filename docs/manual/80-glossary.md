# 名詞對照

| 名詞 | 說明 |
| --- | --- |
| artifact | 回測、驗證或比較流程留下的 result、CSV、JSON、summary 等證據檔或 DB payload |
| canonical candles | 經 canonical policy 選出的 K 線資料，通常由 DB path 提供 |
| DB parity | 驗證 artifact price/funding/external observations 是否能與 DB 來源對上 |
| `ct_val` | contract value；影響 notional、PnL、funding、margin、liquidation |
| DSR | Deflated Sharpe Ratio；用來處理多次嘗試後的 Sharpe 偏誤 |
| PSR | Probabilistic Sharpe Ratio；估計 Sharpe 是否達標的機率 |
| CPCV | Combinatorial Purged Cross-Validation；用 purge/embargo 降低 leakage |
| walk-forward | 依時間滾動 train/test 的驗證方式 |
| purge / embargo | 在 train/test 切分附近移除或隔離樣本，降低 leakage |
| `n_trials` | 策略或參數嘗試次數；需要誠實計入人工調參與未保留 artifact 的嘗試 |
| idealized fill | 理想化成交假設；不可當 promotion 或 live readiness evidence |
| `strategy_fill` | strategy-side fill profile；用於研究敏感度，不可滿足部署 Gate |
| `dual_output` | 同時輸出 strategy-fill 與 realistic-execution 子 run 的比較模式 |
| portable validation | 以外部/reference engine 交叉檢查策略 signal logic 的驗證 |
| source data validation | 檢查 artifact 使用的資料來源、coverage、DB parity、funding/external observations |
| funding cashflow | 永續合約 funding 對資金曲線的現金流影響 |
| maker / post-only | 以 maker 掛單為主的執行假設；post-only 可避免 taker 成交 |
| fill rate | signal/order 轉成實際成交的比例 |
| promotion gate | 策略往 demo、shadow 或 live 前必須通過的審查條件 |
| shadow / demo / live | shadow 是不實際下單或隔離觀察；demo 是交易所模擬；live 是真實資金 |
| `STATUS.md` | Progress panel 的 branch board 來源；只描述進度，不改變策略或 gate |
