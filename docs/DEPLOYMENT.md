# Deployment and Runbook

## Local Workspace Deployment

From PowerShell in project root:

```powershell
./scripts/deploy_local.ps1 -IndexFile data_out/2026-05-05-sample.jsonl -Port 8000
```

Health check:

```powershell
curl http://127.0.0.1:8000/health
```

Ask endpoint:

```powershell
curl -Method POST http://127.0.0.1:8000/ask -ContentType "application/json" -Body '{"question":"Vad sägs om AI-satsningarna?","top_k":3}'
```

## Investigation Build Command

If index already exists:

```powershell
./scripts/run_investigation.ps1 -IndexFile data_out/2026-05-05-sample.jsonl
```

If you need ingestion from source folder:

```powershell
./scripts/run_investigation.ps1 -SourcePath /home/demo/data/2026-05-05 -IndexFile data_out/2026-05-05-sample.jsonl -MaxFiles 120
```

## SSH Host Deployment (Current Working Path)

```bash
cd ~/region-agent
source .venv/bin/activate
export APP_INDEX=data_out/2026-05-05-sample.jsonl
uvicorn app.server:app --host 127.0.0.1 --port 8000
```
