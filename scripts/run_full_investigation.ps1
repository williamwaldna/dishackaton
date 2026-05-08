Param(
    [string]$SourcePath = "",
    [string]$IndexFile = "data_out/2026-05-05-sample.jsonl",
    [int]$MaxFiles = 120,
    [switch]$EnableLLM = $false,
    [switch]$EnableConnections = $false,
    [int]$ConnectionsSampleSize = 20
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Set-Location "$PSScriptRoot\.."

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logFile = "data_out/investigation_log_$timestamp.txt"
"Investigation Pipeline Log - $timestamp" | Out-File -FilePath $logFile -Encoding UTF8

function Log-Message {
    param([string]$Message, [string]$Color = "White")
    Write-Host $Message -ForegroundColor $Color
    $Message | Out-File -FilePath $logFile -Encoding UTF8 -Append
}

function Show-MachineStats {
    param([string]$Title)

    Log-Message ""
    Log-Message "--------------------------------------------------" "Cyan"
    Log-Message "MACHINE RESOURCE USAGE - $Title" "Cyan"
    Log-Message "--------------------------------------------------" "Cyan"

    $cpuInfo = Get-CimInstance Win32_Processor | Select-Object -First 1
    Log-Message "Processor: $($cpuInfo.Name)" "Gray"
    Log-Message "Cores: $($cpuInfo.NumberOfCores) | Threads: $($cpuInfo.NumberOfLogicalProcessors)" "Gray"

    try {
        $counter = Get-Counter '\Processor(_Total)\% Processor Time' -SampleInterval 1 -MaxSamples 1
        $cpuLoad = [math]::Round(($counter.CounterSamples | Select-Object -First 1).CookedValue, 2)
        Log-Message "CPU Load: $cpuLoad%" "Gray"
    }
    catch {
        Log-Message "CPU Load: unavailable" "Gray"
    }

    $osInfo = Get-CimInstance Win32_OperatingSystem
    $totalMemMB = [math]::Round($osInfo.TotalVisibleMemorySize / 1024, 2)
    $freeMemMB = [math]::Round($osInfo.FreePhysicalMemory / 1024, 2)
    $usedMemMB = [math]::Round($totalMemMB - $freeMemMB, 2)
    $memPercent = if ($totalMemMB -gt 0) { [math]::Round(($usedMemMB / $totalMemMB) * 100, 2) } else { 0 }
    Log-Message "Memory: $usedMemMB MB / $totalMemMB MB ($memPercent%)" "Gray"

    $pyProcs = Get-Process python -ErrorAction SilentlyContinue
    if ($pyProcs) {
        $pythonMemMB = [math]::Round((($pyProcs | Measure-Object WorkingSet -Sum).Sum) / 1MB, 2)
        Log-Message "Python Working Set: $pythonMemMB MB" "Yellow"
    }
}

if (!(Test-Path ".venv")) {
    Log-Message "Creating Python virtual environment..." "Cyan"
    py -3 -m venv .venv
}

. .\.venv\Scripts\Activate.ps1
Log-Message "Virtual environment activated." "Green"

if (Test-Path ".env") {
    Log-Message "Loading environment variables from .env" "Cyan"
    Get-Content .env | ForEach-Object {
        if ($_ -and $_ -notmatch '^\s*#' -and $_ -match '=') {
            $parts = $_ -split '=', 2
            if ($parts.Count -eq 2) {
                [Environment]::SetEnvironmentVariable($parts[0].Trim(), $parts[1].Trim())
            }
        }
    }
}

Show-MachineStats "BEFORE"

if ($SourcePath -ne "") {
    Log-Message "Running ingestion..." "Cyan"
    python app/ingest.py --source $SourcePath --out $IndexFile --max-files $MaxFiles | Tee-Object -FilePath $logFile -Append
    Show-MachineStats "AFTER INGEST"
}

Log-Message "Running investigation..." "Cyan"
$investigateArgs = @("app/investigate.py", "--index", $IndexFile, "--out-dir", "data_out")
if ($EnableLLM) { $investigateArgs += "--llm" }
python @investigateArgs | Tee-Object -FilePath $logFile -Append
Show-MachineStats "AFTER INVESTIGATE"

if ($EnableConnections) {
    Log-Message "Running hidden connections analysis..." "Cyan"
    $connectionArgs = @("app/analyze_connections.py", "--index", $IndexFile, "--out-dir", "data_out", "--sample-size", "$ConnectionsSampleSize")
    if ($EnableLLM) { $connectionArgs += "--llm" }
    python @connectionArgs | Tee-Object -FilePath $logFile -Append
    Show-MachineStats "AFTER CONNECTIONS"
}

Log-Message "Generating visualizations..." "Cyan"
python app/visualize.py --out-dir data_out | Tee-Object -FilePath $logFile -Append
Show-MachineStats "FINAL"

Log-Message ""
Log-Message "Pipeline complete." "Green"
Log-Message "Log file: $logFile" "Green"
