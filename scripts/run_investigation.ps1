Param(
    [string]$SourcePath = "",
    [string]$IndexFile = "data_out/2026-05-05-sample.jsonl",
    [int]$MaxFiles = 120
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

if ($SourcePath -ne "") {
    python app/ingest.py --source $SourcePath --out $IndexFile --max-files $MaxFiles
}

python app/investigate.py --index $IndexFile --out-dir data_out
python app/visualize.py --out-dir data_out

Write-Host "Investigation outputs:" -ForegroundColor Green
Write-Host "- data_out/investigation_findings.md"
Write-Host "- data_out/investigation_nodes.csv"
Write-Host "- data_out/investigation_edges.csv"
Write-Host "- data_out/topic_timeline.csv"
Write-Host "- data_out/timeline.html"
Write-Host "- data_out/graph.html"
