Param(
    [string]$SourcePath = "",
    [string]$IndexFile = "data_out/2026-05-05-sample.jsonl",
    [int]$MaxFiles = 120,
    [switch]$EnableLLM = $false
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

# Load .env file if it exists
if (Test-Path ".env") {
    Get-Content .env | ForEach-Object {
        if ($_ -match '^\s*([^=]+)=(.*)$') {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim()
            [Environment]::SetEnvironmentVariable($name, $value)
        }
    }
    Write-Host "Loaded environment variables from .env" -ForegroundColor Cyan
}

if ($SourcePath -ne "") {
    Write-Host "`n📂 Starting ingestion..." -ForegroundColor Cyan
    python app/ingest.py --source $SourcePath --out $IndexFile --max-files $MaxFiles
}

Write-Host "`n🔍 Running investigation..." -ForegroundColor Cyan
$llmFlag = if ($EnableLLM) { "--llm" } else { "" }
python app/investigate.py --index $IndexFile --out-dir data_out $llmFlag

Write-Host "`n🎨 Generating visualizations..." -ForegroundColor Cyan
python app/visualize.py --out-dir data_out

Write-Host "`n✨ Investigation complete!" -ForegroundColor Green
Write-Host "`nOutputs saved to data_out/:" -ForegroundColor Green
Write-Host "- investigation_findings.md (with analysis)"
Write-Host "- investigation_nodes.csv (graph nodes)"
Write-Host "- investigation_edges.csv (graph edges)"
Write-Host "- topic_timeline.csv (timeline data)"
Write-Host "- timeline.html (interactive timeline - open in browser)"
Write-Host "- graph.html (interactive network graph - open in browser)"
