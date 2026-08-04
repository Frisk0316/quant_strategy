param(
    [Parameter(Mandatory)]
    [ValidateSet(
        "test-unit", "test-lab", "test-integration", "check-config", "lint",
        "docs-check", "docs-impact", "frontend-check", "api-smoke",
        "backtest-smoke", "verify", "verify-full"
    )]
    [string]$Target
)

$ErrorActionPreference = "Stop"

function Get-Tool([string]$Name, [string]$Default) {
    $value = [Environment]::GetEnvironmentVariable($Name)
    if ([string]::IsNullOrWhiteSpace($value)) { return $Default }
    return $value
}

function New-Step([string]$FilePath, [string[]]$Arguments) {
    [pscustomobject]@{ FilePath = $FilePath; Arguments = $Arguments }
}

function Invoke-Step($Step) {
    $filePath = $Step.FilePath
    $arguments = $Step.Arguments
    Write-Host ("> {0} {1}" -f $filePath, ($arguments -join " "))
    try {
        & $filePath @arguments
    }
    catch {
        Write-Error $_
        exit 1
    }
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

$python = Get-Tool "PYTHON" "python"
$pytest = Get-Tool "PYTEST" "pytest"
$ruff = Get-Tool "RUFF" "ruff"
$node = Get-Tool "NODE" "node"

$steps = @{
    "test-unit" = New-Step $pytest @("tests/unit/", "-v", "--tb=short")
    "test-lab" = New-Step $pytest @("research/crypto-alpha-lab/tests", "-q", "-p", "no:cacheprovider")
    "test-integration" = New-Step $pytest @("tests/integration/", "-v", "--tb=short")
    "check-config" = New-Step $python @("scripts/validate_pipeline.py", "--check-config-only")
    "lint" = New-Step $ruff @("check", "src/", "tests/", "backtesting/", "scripts/")
    "docs-check" = @(
        New-Step $python @("scripts/docs/check_doc_metadata.py")
        New-Step $python @("scripts/docs/check_feature_map_links.py")
        New-Step $python @("scripts/docs/check_ledger_consistency.py")
    )
    "docs-impact" = New-Step $python @("scripts/docs/check_doc_impact.py")
    "frontend-check" = @(
        "frontend/data.js",
        "frontend/tweaks-panel.js",
        "frontend/charts.js",
        "frontend/view-config.js",
        "frontend/view-backtest.js",
        "frontend/view-results.js",
        "frontend/view-validation.js",
        "frontend/view-trades.js",
        "frontend/view-glossary.js",
        "frontend/view-manual.js",
        "frontend/view-progress.js",
        "frontend/view-ledger.js",
        "frontend/view-research.js",
        "frontend/app.js"
    ) | ForEach-Object { New-Step $node @("--check", $_) }
    "api-smoke" = New-Step $python @("scripts/smoke/api_smoke.py")
    "backtest-smoke" = New-Step $python @("scripts/smoke/backtest_smoke.py")
    "validate-data" = New-Step $python @("scripts/validate_pipeline.py", "--data-dir", "data/ticks", "--inst", "BTC-USDT-SWAP")
}

$order = @{
    "verify" = @(
        "lint", "docs-check", "frontend-check", "check-config",
        "test-unit", "test-lab", "api-smoke", "backtest-smoke"
    )
    "verify-full" = @(
        "lint", "docs-check", "frontend-check", "check-config",
        "test-unit", "test-lab", "api-smoke", "backtest-smoke",
        "test-integration", "validate-data"
    )
}

$targetSteps = if ($order.ContainsKey($Target)) { $order[$Target] } else { @($Target) }
foreach ($stepName in $targetSteps) {
    Write-Host "==> $stepName"
    foreach ($step in @($steps[$stepName])) { Invoke-Step $step }
}
