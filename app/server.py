import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel

from app.query import load_records, search

load_dotenv()

APP_INDEX = Path(os.getenv("APP_INDEX", "data_out/2026-05-05.jsonl"))
records = load_records(APP_INDEX) if APP_INDEX.exists() else []

app = FastAPI(title="Region Agent API", version="0.1.0")


class AskRequest(BaseModel):
    question: str
    top_k: int = 5


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True, "records": len(records), "index": str(APP_INDEX)}


@app.post("/ask")
def ask(req: AskRequest) -> dict[str, Any]:
    if not records:
        return {"answer": "No index loaded. Run ingest first.", "sources": []}

    hits = search(records, req.question, req.top_k)
    answer = "\n".join(
        [f"- {h['meeting_date']} | {h['case_id']} | {h['document_type']} | {h['document_path']}" for h in hits]
    )
    return {"answer": "Most relevant documents found:", "sources": hits, "summary": answer}
