Param(
    [string]$OutDir = "data_out",
    [string]$IndexFile = "data_out/2026-05-05-sample.jsonl",
    [int]$Port = 8501
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Set-Location "$PSScriptRoot\.."

if (!(Test-Path ".venv")) {
    py -3 -m venv .venv
}

$pythonExe = Join-Path (Get-Location) ".venv\Scripts\python.exe"

& $pythonExe -m pip install -r requirements.txt

$env:APP_INDEX = $IndexFile

Write-Host "Starting Streamlit dashboard on http://127.0.0.1:$Port" -ForegroundColor Green
& $pythonExe -m streamlit run app/dashboard.py --server.port $Port --server.address 127.0.0.1
