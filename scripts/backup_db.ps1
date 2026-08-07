# Weekly logical backup of the quant TimescaleDB (compose service `timescaledb`,
# published on 127.0.0.1:5432). Writes outside the repo so nothing can be committed.
#
# ponytail: skips market_klines chunk data (user ruling 2026-08-07: re-downloadable venue
# klines, ~10 GB even compressed). Everything irreplaceable (external_observations, funding,
# registries, backtest artifact rows) is included. Columnstore compression (2026-08-06) moved
# most chunk data into compress_hyper_* tables, so BOTH chunk prefixes must be excluded —
# excluding only _hyper_* would silently dump the compressed data anyway.
#
# Restore: pg_restore -h 127.0.0.1 -U quant -d <target> --clean --if-exists <dump>
# then re-ingest market_klines from Binance/OKX archives.
$ErrorActionPreference = 'Stop'

$Dir       = 'C:\quant_backups'
$Keep      = 2
$MinFreeGB = 20
$Bin       = 'C:\Program Files\PostgreSQL\18\bin'
$EnvFile   = 'C:\quant_strategy\.env'

$match = Select-String -Path $EnvFile -Pattern '^TIMESCALE_PASSWORD=(.+)$'
if (-not $match) { throw "TIMESCALE_PASSWORD not found in $EnvFile" }
$env:PGPASSWORD = $match.Matches[0].Groups[1].Value.Trim()

$freeGB = (Get-PSDrive C).Free / 1GB
if ($freeGB -lt $MinFreeGB) { throw ("Aborting: only {0:N1} GB free on C:" -f $freeGB) }

New-Item -ItemType Directory -Force -Path $Dir | Out-Null

# Chunk tables are named by hypertable id, so resolve both ids instead of hardcoding.
$prefixes = ((& "$Bin\psql.exe" -h 127.0.0.1 -U quant -d quant -tAc "select '_hyper_'||id||'|'||coalesce('compress_hyper_'||compressed_hypertable_id,'') from _timescaledb_catalog.hypertable where table_name='market_klines'").Trim() -split '\|') | Where-Object { $_ }
if (-not $prefixes -or ($prefixes | Where-Object { $_ -notmatch '^(_hyper|compress_hyper)_\d+$' })) { throw "Unexpected market_klines chunk prefixes: '$prefixes'" }
$excludes = $prefixes | ForEach-Object { "--exclude-table-data=_timescaledb_internal.${_}_*_chunk" }

$out = Join-Path $Dir ('quant-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.dump')
& "$Bin\pg_dump.exe" -h 127.0.0.1 -U quant -d quant -Fc @excludes -f $out
if ($LASTEXITCODE -ne 0) { Remove-Item $out -Force -ErrorAction SilentlyContinue; throw "pg_dump failed ($LASTEXITCODE)" }

# A dump nobody can read is not a backup. Prove the archive parses before pruning old ones.
& "$Bin\pg_restore.exe" --list $out > $null
if ($LASTEXITCODE -ne 0) { Remove-Item $out -Force -ErrorAction SilentlyContinue; throw "dump is unreadable, discarded" }

Get-ChildItem $Dir -Filter 'quant-*.dump' | Sort-Object LastWriteTime -Descending | Select-Object -Skip $Keep | Remove-Item -Force

"OK {0} ({1:N1} GB)" -f $out, ((Get-Item $out).Length / 1GB)
