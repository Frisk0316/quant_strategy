# Weekly logical backup of the quant TimescaleDB (compose service `timescaledb`,
# published on 127.0.0.1:5432). Writes outside the repo so nothing can be committed.
#
# ponytail: skips market_klines chunk data. 51 of the 78 GB is raw venue klines that can be
# re-downloaded from Binance/OKX; everything irreplaceable (external_observations, funding,
# registries, backtest artifact rows) is included. Drop the --exclude-table-data argument if
# you ever want a byte-complete restore with no re-ingest, and budget ~3x the disk.
#
# Restore: pg_restore -h 127.0.0.1 -U quant -d <target> --clean --if-exists <dump>
$ErrorActionPreference = 'Stop'

$Dir       = 'C:\quant_backups'
$Keep      = 3
$MinFreeGB = 20
$Bin       = 'C:\Program Files\PostgreSQL\18\bin'
$EnvFile   = 'C:\quant_strategy\.env'

$match = Select-String -Path $EnvFile -Pattern '^TIMESCALE_PASSWORD=(.+)$'
if (-not $match) { throw "TIMESCALE_PASSWORD not found in $EnvFile" }
$env:PGPASSWORD = $match.Matches[0].Groups[1].Value.Trim()

$freeGB = (Get-PSDrive C).Free / 1GB
if ($freeGB -lt $MinFreeGB) { throw ("Aborting: only {0:N1} GB free on C:" -f $freeGB) }

New-Item -ItemType Directory -Force -Path $Dir | Out-Null

# Chunk tables are named by hypertable id, so resolve it instead of hardcoding _hyper_9.
$prefix = (& "$Bin\psql.exe" -h 127.0.0.1 -U quant -d quant -tAc "select '_hyper_'||id from _timescaledb_catalog.hypertable where table_name='market_klines'").Trim()
if ($prefix -notmatch '^_hyper_\d+$') { throw "Unexpected market_klines chunk prefix: '$prefix'" }

$out = Join-Path $Dir ('quant-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.dump')
& "$Bin\pg_dump.exe" -h 127.0.0.1 -U quant -d quant -Fc --exclude-table-data="_timescaledb_internal.${prefix}_*_chunk" -f $out
if ($LASTEXITCODE -ne 0) { Remove-Item $out -Force -ErrorAction SilentlyContinue; throw "pg_dump failed ($LASTEXITCODE)" }

# A dump nobody can read is not a backup. Prove the archive parses before pruning old ones.
& "$Bin\pg_restore.exe" --list $out > $null
if ($LASTEXITCODE -ne 0) { Remove-Item $out -Force -ErrorAction SilentlyContinue; throw "dump is unreadable, discarded" }

Get-ChildItem $Dir -Filter 'quant-*.dump' | Sort-Object LastWriteTime -Descending | Select-Object -Skip $Keep | Remove-Item -Force

"OK {0} ({1:N1} GB)" -f $out, ((Get-Item $out).Length / 1GB)
