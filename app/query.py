import argparse
import json
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def load_records(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def search(records, query: str, k: int):
    docs = [r["text"] for r in records]
    vectorizer = TfidfVectorizer(max_features=120000, stop_words=None)
    x = vectorizer.fit_transform(docs)
    q = vectorizer.transform([query])
    sim = cosine_similarity(q, x).flatten()
    top_idx = sim.argsort()[::-1][:k]

    hits = []
    for i in top_idx:
        r = records[int(i)]
        hits.append(
            {
                "score": float(sim[int(i)]),
                "meeting_date": r.get("meeting_date"),
                "case_id": r.get("case_id"),
                "document_type": r.get("document_type"),
                "document_path": r.get("document_path"),
                "snippet": r.get("text", "")[:700].replace("\n", " "),
            }
        )
    return hits


def main():
    parser = argparse.ArgumentParser(description="Local retrieval over ingested JSONL")
    parser.add_argument("--index", required=True, help="Path to JSONL from ingest.py")
    parser.add_argument("--query", required=True, help="Question text")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    records = load_records(Path(args.index))
    hits = search(records, args.query, args.top_k)

    print(f"Top {len(hits)} hits for: {args.query}")
    for n, h in enumerate(hits, start=1):
        print("=" * 100)
        print(f"[{n}] score={h['score']:.4f} date={h['meeting_date']} case={h['case_id']} type={h['document_type']}")
        print(f"path: {h['document_path']}")
        print(h["snippet"])


if __name__ == "__main__":
    main()
