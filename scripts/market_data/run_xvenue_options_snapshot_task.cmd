@echo off
rem H-039 forward-only hourly OKX/Bybit/Deribit option-IV snapshots.
cd /d C:\quant_strategy
if not exist logs mkdir logs
call scripts\_load_dotenv.cmd
"C:\Users\woody\AppData\Local\Programs\Python\Python312\python.exe" scripts\market_data\snapshot_xvenue_options.py >> logs\xvenue_options_snapshot.log 2>&1
exit /b %ERRORLEVEL%
