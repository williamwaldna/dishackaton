# Region Investigative Agent

This workspace contains an investigative AI workflow for Region Stockholm meeting archives.

## What It Does

- Ingests and normalizes PDF documents.
- Retrieves evidence for user questions.
- Builds a relationship graph (documents, cases, topics, people).
- Detects risk signals and creates investigation findings.
- Produces visual outputs for timeline and graph analysis.

## Project Structure

- `app/ingest.py`: PDF to JSONL ingestion.
- `app/query.py`: retrieval engine for question-driven search.
- `app/server.py`: API endpoints (`/health`, `/ask`).
- `app/investigate.py`: graph + findings extraction.
- `app/visualize.py`: HTML visual generation.
- `scripts/run_investigation.ps1`: one-command investigation workflow.
- `scripts/deploy_local.ps1`: local API deployment script.
- `docs/`: workflow, deployment, and session documentation.

## Quick Start (PowerShell)

```powershell
cd C:\Users\UR246U\VS\HP_HACATHON_26\region-agent
./scripts/run_investigation.ps1 -IndexFile data_out/2026-05-05-sample.jsonl
./scripts/deploy_local.ps1 -IndexFile data_out/2026-05-05-sample.jsonl -Port 8000
```

## Investigation Outputs

- `data_out/investigation_findings.md`
- `data_out/investigation_nodes.csv`
- `data_out/investigation_edges.csv`
- `data_out/topic_timeline.csv`
- `data_out/timeline.html`
- `data_out/graph.html`

## API Usage

```powershell
curl http://127.0.0.1:8000/health
curl -Method POST http://127.0.0.1:8000/ask -ContentType "application/json" -Body '{"question":"Vad sägs om AI-satsningarna?","top_k":3}'
```
