"""
Advanced LLM-powered connection analyzer for finding hidden investigative links.
Uses OpenAI to find patterns and relationships not captured by simple graph construction.
"""
import argparse
import json
import os
import time
from pathlib import Path
from typing import Optional

import pandas as pd
from openai import OpenAI


def analyze_document_pair_connection(client, doc1: dict, doc2: dict, context_topics: list) -> Optional[str]:
    """Use LLM to analyze hidden connections between two documents."""
    prompt = f"""Analyze these two Swedish regional government documents and find hidden investigative connections:

DOCUMENT 1:
Title: {doc1.get('document_title', 'N/A')}
Case: {doc1.get('case_id', 'N/A')}
Date: {doc1.get('meeting_date', 'N/A')}
Type: {doc1.get('document_type', 'N/A')}
Excerpt: {doc1.get('text', '')[:500]}

DOCUMENT 2:
Title: {doc2.get('document_title', 'N/A')}
Case: {doc2.get('case_id', 'N/A')}
Date: {doc2.get('meeting_date', 'N/A')}
Type: {doc2.get('document_type', 'N/A')}
Excerpt: {doc2.get('text', '')[:500]}

Common Topics: {', '.join(context_topics)}

Provide a brief investigative analysis (max 150 words) explaining:
1. Direct connections (shared topics, people, cases)
2. Hidden patterns (temporal, thematic, policy implications)
3. Governance concerns or contradictions
4. Risk signals from the combination of both documents

Be concise and actionable for an investigator."""

    try:
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert Swedish governmental analyst specializing in finding hidden connections and anomalies in policy documents."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.6,
            max_tokens=300,
        )
        return response.choices[0].message.content
    except Exception as e:
        return None


def extract_topics_from_text(text: str) -> list:
    """Extract key Swedish governance terms from text."""
    keywords = [
        "ai", "artificiell", "automatisering",
        "budget", "kostnad", "miljon",
        "vård", "sjukvård", "patient",
        "trafik", "buss", "transport",
        "upphandling", "styrning", "risk", "revision"
    ]
    found = [kw for kw in keywords if kw in text.lower()]
    return found


def find_hidden_connections(records: list, sample_size: int = 20, llm_enabled: bool = True) -> dict:
    """Find hidden investigative connections using LLM."""
    api_key = os.getenv("OPENAI_API_KEY")
    if llm_enabled and not api_key:
        print("⚠️  OPENAI_API_KEY not set. Skipping LLM connection analysis.")
        return {"connections": [], "analysis_count": 0}
    
    client = OpenAI(api_key=api_key) if llm_enabled else None
    
    connections = []
    analysis_count = 0
    
    # Sample document pairs for analysis (expensive operation)
    for i in range(min(sample_size, len(records))):
        for j in range(i + 1, min(i + 5, len(records))):  # Compare each doc to next 4
            doc_i = records[i]
            doc_j = records[j]
            
            # Skip if same case (already connected)
            if doc_i.get("case_id") == doc_j.get("case_id"):
                continue
            
            # Extract common topics
            topics_i = set(extract_topics_from_text(doc_i.get("text", "")))
            topics_j = set(extract_topics_from_text(doc_j.get("text", "")))
            common = list(topics_i & topics_j)
            
            # Analyze with LLM if topics overlap
            if common and llm_enabled:
                analysis = analyze_document_pair_connection(client, doc_i, doc_j, common)
                if analysis:
                    connections.append({
                        "doc1_id": i,
                        "doc1_title": doc_i.get("document_title", f"doc_{i}"),
                        "doc1_case": doc_i.get("case_id"),
                        "doc2_id": j,
                        "doc2_title": doc_j.get("document_title", f"doc_{j}"),
                        "doc2_case": doc_j.get("case_id"),
                        "common_topics": ", ".join(common),
                        "hidden_connection_analysis": analysis
                    })
                    analysis_count += 1
    
    return {
        "connections": connections,
        "analysis_count": analysis_count
    }


def generate_connection_report(connections_data: dict, output_path: Path):
    """Generate markdown report of hidden connections."""
    lines = [
        "# Hidden Investigative Connections Report",
        "",
        f"**Analysis Timestamp**: {pd.Timestamp.now().isoformat()}",
        f"**Connections Found**: {len(connections_data['connections'])}",
        "",
    ]
    
    if connections_data['connections']:
        lines.extend([
            "## Document Pair Analyses",
            "",
        ])
        
        for idx, conn in enumerate(connections_data['connections'], 1):
            lines.extend([
                f"### Connection {idx}",
                "",
                f"**Document 1**: {conn['doc1_title']} ({conn['doc1_case']})",
                f"**Document 2**: {conn['doc2_title']} ({conn['doc2_case']})",
                f"**Common Topics**: {conn['common_topics']}",
                "",
                "**Analysis**:",
                conn['hidden_connection_analysis'],
                "",
            ])
    else:
        lines.append("No hidden connections analyzed (insufficient common topics or LLM disabled).")
    
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Find hidden investigative connections between documents")
    parser.add_argument("--index", required=True, help="Path to JSONL index")
    parser.add_argument("--out-dir", default="data_out", help="Output directory")
    parser.add_argument("--sample-size", type=int, default=20, help="Number of documents to analyze")
    parser.add_argument("--llm", action="store_true", help="Enable LLM analysis (requires OPENAI_API_KEY)")
    args = parser.parse_args()
    
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    print("\n" + "="*60)
    print("🔗 HIDDEN CONNECTION ANALYZER")
    print("="*60)
    
    # Load records
    print("\n📂 Loading records...")
    load_start = time.time()
    with open(args.index, "r", encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]
    load_time = time.time() - load_start
    print(f"   ✅ Loaded {len(records)} documents in {load_time:.2f}s")
    
    # Analyze connections
    print(f"\n🔍 Analyzing hidden connections (sample size: {args.sample_size})...")
    analysis_start = time.time()
    connections = find_hidden_connections(records, sample_size=args.sample_size, llm_enabled=args.llm)
    analysis_time = time.time() - analysis_start
    print(f"   ✅ Analysis complete in {analysis_time:.2f}s")
    print(f"      - {connections['analysis_count']} connections analyzed")
    
    # Write report
    print("\n💾 Writing connection report...")
    output_file = out_dir / "hidden_connections_analysis.md"
    generate_connection_report(connections, output_file)
    print(f"   ✅ Report saved: {output_file}")
    
    print("\n" + "="*60)
    print("✨ Connection analysis complete!")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
