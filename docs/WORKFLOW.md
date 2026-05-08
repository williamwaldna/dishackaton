# Investigative Agent Workflow

## Objective

Turn meeting-document archives into an investigation pipeline that can:

- detect recurring risks and hidden links,
- map relationships between cases and actors,
- produce evidence-based narrative summaries.

## End-to-End Steps

1. Ingest PDF documents into normalized JSONL records using `app/ingest.py`.
2. Run retrieval for targeted questions using `app/query.py`.
3. Build a relationship graph and risk findings using `app/investigate.py`.
4. Generate visual assets (`timeline.html`, `graph.html`) using `app/visualize.py`.
5. Serve API endpoints with `app/server.py` for integration with UI or tools.

## Investigative Signals Produced

- Topic concentration over time.
- Cases with high cross-references.
- Cases with unusually high document volume.
- Risk-term-heavy documents for manual review.
- Most-mentioned people and case/topic link density.

## Primary Outputs

- `data_out/investigation_findings.md`
- `data_out/investigation_nodes.csv`
- `data_out/investigation_edges.csv`
- `data_out/topic_timeline.csv`
- `data_out/timeline.html`
- `data_out/graph.html`
