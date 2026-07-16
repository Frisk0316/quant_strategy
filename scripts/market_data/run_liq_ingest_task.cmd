@echo off
rem OKX liquidation forward-accumulation (P5). Scheduled every 2h because the
rem public REST window is only hours deep (BTC ~14h, ETH ~5h measured
rem 2026-07-03); see docs/RUNBOOK.md and tasks/2026-07-03-pipeline-improvement-tasks.md.
cd /d C:\quant_strategy
if not exist logs mkdir logs
"C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe" scripts\market_data\ingest_external.py --dataset liq_okx_btc --dataset liq_okx_eth >> logs\liq_okx_ingest.log 2>&1
