Param(
    [string]$IndexFile = "data_out/2026-05-05-sample.jsonl",
    [int]$Port = 8000
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Set-Location "$PSScriptRoot\.."

if (!(Test-Path ".venv")) {
    py -3 -m venv .venv
}

. .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt

if (!(Test-Path $IndexFile)) {
    Write-Host "Index file not found: $IndexFile" -ForegroundColor Yellow
    Write-Host "Run ingestion first using app/ingest.py." -ForegroundColor Yellow
    exit 1
}

$env:APP_INDEX = $IndexFile
Write-Host "Starting API on http://127.0.0.1:$Port" -ForegroundColor Green
uvicorn app.server:app --host 127.0.0.1 --port $Port
