@echo off
rem Public OKX books/trades/funding collector. No credentials and no order path.
cd /d C:\quant_strategy
if not exist logs mkdir logs
echo [%date% %time%] task starting as %USERNAME% >> logs\okx_market_data_collector.log
if not exist "C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe" exit /b 2
"C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe" scripts\stream_orderbook.py --duration 0 --symbols BTC-USDT-SWAP BTC-USDT ETH-USDT-SWAP ETH-USDT >> logs\okx_market_data_collector.log 2>&1
set "collector_exit=%ERRORLEVEL%"
echo [%date% %time%] collector exited with %collector_exit% >> logs\okx_market_data_collector.log
exit /b %collector_exit%
