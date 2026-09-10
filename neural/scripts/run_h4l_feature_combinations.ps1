[CmdletBinding()]
param(
    [ValidateRange(42, 46)]
    [int]$Seed = 42,

    [string]$ConfigPath = "config/research_feature_combinations_seed42.json",

    [string]$PreparedRun,

    [string]$GateRun,

    [string]$T1Validation,

    [string]$OutputRoot,

    [string]$PythonCommand = "python",

    [switch]$PlanOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
Set-Location -LiteralPath $projectRoot

function Resolve-ProjectPath {
    param([Parameter(Mandatory = $true)][string]$Value)
    if ([IO.Path]::IsPathRooted($Value)) {
        return [IO.Path]::GetFullPath($Value)
    }
    return [IO.Path]::GetFullPath((Join-Path $projectRoot $Value))
}

function Select-Value {
    param([string]$Override, [object]$Configured)
    if (-not [string]::IsNullOrWhiteSpace($Override)) {
        return $Override
    }
    return [string]$Configured
}

$configFile = Resolve-ProjectPath $ConfigPath
if (-not (Test-Path -LiteralPath $configFile -PathType Leaf)) {
    throw "Batch configuration does not exist: $configFile"
}
$config = Get-Content -LiteralPath $configFile -Raw | ConvertFrom-Json

$expectedCombinations = @("A", "B", "C", "D", "AB", "AC", "AD", "BC", "BD", "CD", "ABC", "ABD", "ACD", "BCD", "ABCD")
$configuredCombinations = @($config.feature_combinations)
if ($config.schema_version -ne "h4l-feature-combination-batch-v1" -or
    $config.dataset -ne "atlas2020_4lep" -or
    [int]$config.default_seed -ne 42 -or
    $config.family_id -ne "engineered19_raw_T1" -or
    $config.empty_baseline_candidate -ne "M0c" -or
    $config.combination_candidate -ne "M3" -or
    $config.calibration_transform -ne "raw" -or
    $config.inference_layer -ne "T1" -or
    [double]$config.injection_mu -ne 1.0 -or
    ($configuredCombinations -join ",") -ne ($expectedCombinations -join ",")) {
    throw "Batch configuration differs from the registered single-seed feature-combination contract."
}

$protocol = Resolve-ProjectPath ([string]$config.protocol)
$prepared = Resolve-ProjectPath (Select-Value $PreparedRun $config.prepared_run)
$gate = Resolve-ProjectPath (Select-Value $GateRun $config.g1_gate_run)
$t1 = Resolve-ProjectPath (Select-Value $T1Validation $config.t1_validation)
$configuredOutput = (Select-Value $OutputRoot $config.output_root).Replace("{seed}", [string]$Seed)
$batchRoot = Resolve-ProjectPath $configuredOutput
$runsRoot = Resolve-ProjectPath "runs"

if (-not ($batchRoot.StartsWith($runsRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase))) {
    throw "OutputRoot must be a child of the neural/runs directory."
}
if (-not (Test-Path -LiteralPath $protocol -PathType Leaf)) {
    throw "Research protocol does not exist: $protocol"
}
if (-not $PlanOnly) {
    foreach ($required in @($prepared, $gate, $t1)) {
        if (-not (Test-Path -LiteralPath $required)) {
            throw "Required bound input does not exist: $required"
        }
    }
    if (Test-Path -LiteralPath $batchRoot) {
        throw "OutputRoot already exists and cannot be reused: $batchRoot"
    }
}

function Invoke-Research {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)
    $display = @($PythonCommand, "-m", "src.cli.research") + $Arguments
    Write-Output ($display -join " ")
    if ($PlanOnly) {
        return
    }
    & $PythonCommand -m src.cli.research @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "higgsml-research failed with exit code $LASTEXITCODE"
    }
}

$common = @("--dataset", [string]$config.dataset, "--protocol", $protocol)
$calibrationRuns = [Collections.Generic.List[string]]::new()

$baselineTrain = Join-Path $batchRoot "train/empty"
$baselineCalibration = Join-Path $batchRoot "calibrate/empty"
Invoke-Research (@("train") + $common + @(
    "--input-run", $prepared,
    "--gate-run", $gate,
    "--candidate", "M0c",
    "--seed", [string]$Seed,
    "--run-dir", $baselineTrain
))
Invoke-Research (@("calibrate") + $common + @(
    "--input-run", $prepared,
    "--model-run", $baselineTrain,
    "--transform", "raw",
    "--seed", [string]$Seed,
    "--run-dir", $baselineCalibration
))
$calibrationRuns.Add($baselineCalibration)

foreach ($groups in $expectedCombinations) {
    $trainRun = Join-Path $batchRoot "train/groups-$groups"
    $calibrationRun = Join-Path $batchRoot "calibrate/groups-$groups"
    Invoke-Research (@("train") + $common + @(
        "--input-run", $prepared,
        "--gate-run", $gate,
        "--candidate", "M3",
        "--groups", $groups,
        "--seed", [string]$Seed,
        "--run-dir", $trainRun
    ))
    Invoke-Research (@("calibrate") + $common + @(
        "--input-run", $prepared,
        "--model-run", $trainRun,
        "--transform", "raw",
        "--seed", [string]$Seed,
        "--run-dir", $calibrationRun
    ))
    $calibrationRuns.Add($calibrationRun)
}

$templateRun = Join-Path $batchRoot "templates"
$templateArguments = @("templates") + $common + @(
    "--input-run", $prepared,
    "--t1-validation", $t1,
    "--seed", [string]$Seed,
    "--run-dir", $templateRun
)
foreach ($calibrationRun in $calibrationRuns) {
    $templateArguments += @("--calibration-run", $calibrationRun)
}
Invoke-Research $templateArguments

$inferenceRun = Join-Path $batchRoot "inference"
Invoke-Research (@("infer") + $common + @(
    "--template-run", $templateRun,
    "--layer", "T1",
    "--mu", "1",
    "--seed", [string]$Seed,
    "--run-dir", $inferenceRun
))

$reportRun = Join-Path $batchRoot "report"
Invoke-Research (@("report") + $common + @(
    "--result-run", $inferenceRun,
    "--seed", [string]$Seed,
    "--run-dir", $reportRun
))

if ($PlanOnly) {
    Write-Host "Plan complete: 15 nonempty combinations plus the M0c empty baseline; no run was created."
    return
}

$report = Get-Content -LiteralPath (Join-Path $reportRun "report.json") -Raw | ConvertFrom-Json
$comparisons = @($report.feature_combination_comparisons)
if ($comparisons.Count -ne 1 -or $comparisons[0].status -ne "valid" -or [int]$comparisons[0].seed -ne $Seed) {
    throw "The batch completed, but the complete 15-combination comparison is unavailable. Inspect $reportRun."
}
Write-Host "Completed seed ${Seed}: 15 combination models, M0c baseline, common T1 inference and exact Shapley comparison."
Write-Host "Report: $(Join-Path $reportRun 'report.md')"
