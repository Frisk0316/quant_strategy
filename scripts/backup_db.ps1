# Weekly logical backup of the quant TimescaleDB (compose service `timescaledb`,
# published on 127.0.0.1:5432). Writes outside the repo so nothing can be committed.
#
# Byte-complete: every table, no exclusions. This used to skip market_klines chunk data because
# it was 51 of the 78 GB; columnstore compression (2026-08-06) took the DB to 33 GB, so the
# saving no longer pays for a restore that needs a re-ingest.
#
# Restore: pg_restore -h 127.0.0.1 -U quant -d <target> --clean --if-exists <dump>
$ErrorActionPreference = 'Stop'

$Dir       = 'C:\quant_backups'
# ponytail: Keep=2 because a full dump is ~2x the old partial one and C: has ~95 GB free.
# Raise it if you move $Dir to a bigger drive.
$Keep      = 2
$MinFreeGB = 45
$Bin       = 'C:\Program Files\PostgreSQL\18\bin'
$EnvFile   = 'C:\quant_strategy\.env'

$match = Select-String -Path $EnvFile -Pattern '^TIMESCALE_PASSWORD=(.+)$'
if (-not $match) { throw "TIMESCALE_PASSWORD not found in $EnvFile" }
$env:PGPASSWORD = $match.Matches[0].Groups[1].Value.Trim()

$freeGB = (Get-PSDrive C).Free / 1GB
if ($freeGB -lt $MinFreeGB) { throw ("Aborting: only {0:N1} GB free on C:" -f $freeGB) }

New-Item -ItemType Directory -Force -Path $Dir | Out-Null

$out = Join-Path $Dir ('quant-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.dump')
& "$Bin\pg_dump.exe" -h 127.0.0.1 -U quant -d quant -Fc -f $out
if ($LASTEXITCODE -ne 0) { Remove-Item $out -Force -ErrorAction SilentlyContinue; throw "pg_dump failed ($LASTEXITCODE)" }

# A dump nobody can read is not a backup. Prove the archive parses before pruning old ones.
& "$Bin\pg_restore.exe" --list $out > $null
if ($LASTEXITCODE -ne 0) { Remove-Item $out -Force -ErrorAction SilentlyContinue; throw "dump is unreadable, discarded" }

Get-ChildItem $Dir -Filter 'quant-*.dump' | Sort-Object LastWriteTime -Descending | Select-Object -Skip $Keep | Remove-Item -Force

"OK {0} ({1:N1} GB)" -f $out, ((Get-Item $out).Length / 1GB)
