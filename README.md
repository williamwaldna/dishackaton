# Region Investigative Agent

An AI-powered investigative agent for analyzing Region Stockholm government meeting archives. Uses TF-IDF retrieval, graph analysis, and optional LLM-generated narratives to uncover governance patterns and risk signals.

## What It Does

- **Ingests** PDF documents and extracts metadata (case IDs, dates, types).
- **Retrieves** evidence using TF-IDF similarity for user questions.
- **Investigates** by building knowledge graphs (documents → cases → topics → people).
- **Analyzes** risk signals (budget overruns, delays, contradictions) across meetings.
- **Generates** AI narratives (optional, using OpenAI GPT-4) explaining investigation findings.
- **Visualizes** timelines and network relationships interactively (Plotly HTML).

## Features

### Investigation Pipeline
- **Graph Construction**: ~400 nodes (documents, cases, topics, people) and ~800 edges (relationships)
- **Timeline Analysis**: Topic mentions over time
- **Risk Detection**: Documents flagged with governance concern keywords
- **LLM Narrative**: AI-generated executive summary of findings (optional, requires API key)

### Visualizations
- **Timeline Graph**: Interactive bar chart showing topic frequency over meeting dates
- **Network Graph**: Interactive node-link diagram showing document relationships
- Both auto-open in browser on execution

### Performance
- **Sample Dataset** (64 documents): ~1-2 seconds total execution
- **Full Archive** (4,753+ documents): ~4+ hours single-threaded
- Terminal output shows real-time execution timing for each stage

## Project Structure

```
region-agent/
├── app/
│   ├── ingest.py          # PDF ingestion & JSONL export
│   ├── query.py           # TF-IDF retrieval engine
│   ├── server.py          # FastAPI endpoints
│   ├── investigate.py     # Graph building + LLM narrative
│   ├── visualize.py       # HTML visualization generation
│   └── models.py          # Pydantic data schemas
├── scripts/
│   ├── run_investigation.ps1  # One-command investigation (with LLM flag)
│   └── deploy_local.ps1       # Start local API server
├── docs/
│   ├── WORKFLOW.md        # Step-by-step usage guide
│   ├── DEPLOYMENT.md      # Deployment instructions
│   └── SESSION_LOG.md     # Hackathon session notes
├── .env.example           # Environment variables template
└── requirements.txt       # Python dependencies
```

## Quick Start

### 1. Setup Environment
```powershell
cd region-agent

# Create virtual environment (automatic in script)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### 2. Run Investigation (Without LLM)
```powershell
./scripts/run_investigation.ps1 -IndexFile data_out/2026-05-05-sample.jsonl
```

### 3. Run Investigation (With LLM Narrative)
```powershell
# Set up environment variables
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY

./scripts/run_investigation.ps1 -IndexFile data_out/2026-05-05-sample.jsonl -EnableLLM
```

### 4. View Results
- **Terminal**: Real-time execution summary with timing
- **investigation_findings.md**: Complete findings report (includes LLM narrative if enabled)
- **timeline.html**: Opens automatically in browser (interactive)
- **graph.html**: Opens automatically in browser (drag to explore)

## Terminal Output Example

```
============================================================
🔍 REGIONAL GOVERNMENT INVESTIGATION AGENT
============================================================

📂 Loading records...
   ✅ Loaded 64 documents in 0.23s

🔗 Building investigation graph...
   ✅ Graph built in 0.45s
      - 398 nodes (documents, cases, topics, people)
      - 813 edges (relationships)
      - 5 timeline entries

🤖 Generating LLM narrative...
   ✅ LLM narrative generated successfully in 3.12s

💾 Writing outputs...
   ✅ Files written in 0.18s

📊 INVESTIGATION SUMMARY
------------------------------------------------------------
Top Topics:
   • ai: 12 mentions
   • budget: 8 mentions
   • governance: 7 mentions

Most Mentioned People:
   • Anna Bergström: 5 mentions
   • Lars Pettersson: 4 mentions

Risk-Signal Documents: 15

⏱️  EXECUTION TIME SUMMARY
------------------------------------------------------------
   Load:        0.23s
   Graph:       0.45s
   LLM:         3.12s
   Output:      0.18s
   TOTAL:       4.33s
============================================================
```

## Configuration

### Environment Variables (.env)
```bash
# Required for LLM narrative generation
OPENAI_API_KEY=sk-your-key-here

# Optional
OPENAI_MODEL=gpt-4-turbo  # default: gpt-4-turbo
```

### Command-Line Arguments

**investigate.py**
```
--index FILE        Path to JSONL index (required)
--out-dir DIR       Output directory (default: data_out)
--llm              Generate LLM narrative (requires OPENAI_API_KEY)
```

**visualize.py**
```
--out-dir DIR      Input/output directory (default: data_out)
--no-open          Don't auto-open visualizations in browser
```

## Investigation Outputs

| File | Description |
|------|-------------|
| `investigation_findings.md` | Complete report with statistics and findings (includes LLM narrative if enabled) |
| `investigation_nodes.csv` | Graph nodes (id, label, type, metadata) |
| `investigation_edges.csv` | Graph edges (source, target, relation, weight) |
| `topic_timeline.csv` | Topic frequency per meeting date |
| `timeline.html` | Interactive timeline visualization |
| `graph.html` | Interactive network graph visualization |

## API Usage

### Start Server
```powershell
./scripts/deploy_local.ps1 -IndexFile data_out/2026-05-05-sample.jsonl
```

### Health Check
```powershell
curl http://127.0.0.1:8000/health
```

### Ask Question
```powershell
curl -Method POST http://127.0.0.1:8000/ask `
  -ContentType "application/json" `
  -Body '{
    "question":"Vad sägs om AI-satsningarna?",
    "top_k":3
  }'
```

## Interactive Dashboard (Streamlit)

Run an interactive dashboard with:
- live question answering (API mode or local retrieval mode)
- findings and hidden-connection reports
- embedded interactive timeline and graph visualizations

### Start Dashboard
```powershell
./scripts/run_dashboard.ps1 -OutDir data_out -IndexFile data_out/2026-05-05-sample.jsonl
```

Then open:
- `http://127.0.0.1:8501`

### Notes
- API mode in the dashboard expects `app.server` to be running on `http://127.0.0.1:8000`.
- Local retrieval mode works directly from the JSONL index and does not require the API server.

## How It Works

### 1. Ingestion (ingest.py)
- Reads PDFs from organized folders (date > case > documents)
- Extracts text using pypdf
- Parses metadata (meeting date, case ID, document type)
- Normalizes to JSONL format

### 2. Investigation (investigate.py)
- **Loads** JSONL index into memory
- **Extracts** topics (regex + keyword matching on Swedish terms)
- **Detects** people names using regex NER
- **Builds** graph with nodes for documents, cases, topics, people
- **Connects** with edges for relationships (mentions, references, belongs_to)
- **Analyzes** risk signals (keywords like "risk", "brist", "försening")
- **Generates** narrative (LLM, optional): Uses GPT-4 to summarize findings in executive summary format
- **Outputs**: CSVs and markdown report

### 3. Visualization (visualize.py)
- **Timeline**: Plotly line chart of topic frequency over dates
- **Graph**: NetworkX spring layout rendered as interactive Plotly scatter + lines
- **Browser**: Auto-opens both visualizations (can be disabled with `--no-open`)

### 4. Retrieval (query.py, server.py)
- TF-IDF vectorization of document texts
- Cosine similarity ranking for query matches
- FastAPI endpoints for health checks and question answering

## Technology Stack

- **Language**: Python 3.14
- **PDF**: pypdf
- **Data**: pandas, JSON
- **ML**: scikit-learn (TF-IDF), networkx
- **Visualization**: Plotly
- **API**: FastAPI, Uvicorn
- **LLM**: OpenAI GPT-4 (optional)
- **Schema**: Pydantic

## Development & Debugging

### Local Execution
All scripts work on Windows (PowerShell) with Python 3.10+.

### Remote Execution (SSH)
For full archive processing, use remote Linux host:
```bash
ssh demo@zgx11.local "cd ~/region-agent && \
  python app/investigate.py --index data.jsonl --out-dir data_out --llm"
```

### Logs & Output
- Terminal prints real-time status for each execution stage
- Timing information helps identify bottlenecks
- All outputs saved to `data_out/` with clear file names

## Hackathon Notes

This agent was built during a hackathon to investigate Swedish regional government documents (Region Stockholm). It combines:
- **Lightweight retrieval** (TF-IDF for speed)
- **Graph analysis** (NetworkX for relationships)
- **Visual storytelling** (Plotly for exploration)
- **AI narratives** (LLM for executive summaries)

Goal: Find hidden issues, contradictions, and governance gaps across 4,753+ documents spanning 2023–2026.

---

**For detailed workflows and deployment instructions, see `docs/`**

