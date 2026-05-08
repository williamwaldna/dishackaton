import argparse
import json
import os
import re
import time
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd
from openai import OpenAI


TOPIC_RULES = {
    "ai": ["ai", "artificiell intelligens", "automatisering"],
    "budget": ["budget", "kostnad", "miljon", "statsbidrag", "finans"],
    "healthcare": ["vård", "sjukvård", "patient", "bup", "psykiatri"],
    "transport": ["trafik", "buss", "tunnelbana", "sl", "resenär"],
    "governance": ["upphandling", "styrning", "ansvar", "revision", "risk"],
}

RISK_TERMS = [
    "brist",
    "risk",
    "försening",
    "försening",
    "kostnad",
    "haveri",
    "kris",
    "saknas",
    "otydlig",
]

NAME_PATTERN = re.compile(r"\b[A-ZÅÄÖ][a-zåäöA-ZÅÄÖ\-]+(?:\s+[A-ZÅÄÖ][a-zåäöA-ZÅÄÖ\-]+){1,2}\b")
CASE_PATTERN = re.compile(r"RS[-_]\d{4}-\d+")


def load_records(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def detect_topics(text: str):
    low = text.lower()
    topics = []
    for topic, terms in TOPIC_RULES.items():
        if any(term in low for term in terms):
            topics.append(topic)
    return topics


def extract_people(text: str):
    candidates = NAME_PATTERN.findall(text)
    cleaned = []
    for c in candidates:
        if len(c) < 5:
            continue
        if c.startswith("Region Stockholm"):
            continue
        cleaned.append(c.strip())
    return cleaned


def extract_case_refs(text: str):
    refs = [m.group(0).replace("_", "-") for m in CASE_PATTERN.finditer(text)]
    return sorted(set(refs))


def build_graph(records):
    nodes = []
    edges = []

    def add_node(node_id, label, ntype, attrs=None):
        row = {"id": node_id, "label": label, "type": ntype}
        if attrs:
            row.update(attrs)
        nodes.append(row)

    case_doc_count = Counter()
    case_cross_refs = Counter()
    risk_docs = []
    topic_counter = Counter()
    person_counter = Counter()
    topic_timeline = Counter()

    seen_node_ids = set()

    for idx, record in enumerate(records):
        doc_id = f"doc:{idx}"
        doc_label = record.get("document_title", f"doc_{idx}")
        case_id = record.get("case_id") or "unknown_case"
        meeting_date = record.get("meeting_date") or "unknown_date"
        text = record.get("text", "")

        topics = detect_topics(text)
        people = extract_people(text)
        refs = extract_case_refs(text)

        if doc_id not in seen_node_ids:
            add_node(
                doc_id,
                doc_label,
                "document",
                {
                    "meeting_date": meeting_date,
                    "case_id": case_id,
                    "document_type": record.get("document_type", "document"),
                    "path": record.get("document_path", ""),
                },
            )
            seen_node_ids.add(doc_id)

        case_node = f"case:{case_id}"
        if case_node not in seen_node_ids:
            add_node(case_node, case_id, "case")
            seen_node_ids.add(case_node)

        edges.append({"source": doc_id, "target": case_node, "relation": "belongs_to", "weight": 1})
        case_doc_count[case_id] += 1

        for topic in topics:
            topic_node = f"topic:{topic}"
            if topic_node not in seen_node_ids:
                add_node(topic_node, topic, "topic")
                seen_node_ids.add(topic_node)
            edges.append({"source": doc_id, "target": topic_node, "relation": "mentions_topic", "weight": 1})
            topic_counter[topic] += 1
            topic_timeline[(meeting_date, topic)] += 1

        for person in people[:15]:
            person_node = f"person:{person}"
            if person_node not in seen_node_ids:
                add_node(person_node, person, "person")
                seen_node_ids.add(person_node)
            edges.append({"source": doc_id, "target": person_node, "relation": "mentions_person", "weight": 1})
            person_counter[person] += 1

        for ref in refs:
            ref_node = f"case:{ref}"
            if ref_node not in seen_node_ids:
                add_node(ref_node, ref, "case")
                seen_node_ids.add(ref_node)
            edges.append({"source": doc_id, "target": ref_node, "relation": "references_case", "weight": 1})
            if ref != case_id:
                case_cross_refs[case_id] += 1

        low = text.lower()
        if any(term in low for term in RISK_TERMS):
            risk_docs.append(
                {
                    "meeting_date": meeting_date,
                    "case_id": case_id,
                    "document_path": record.get("document_path", ""),
                    "document_title": doc_label,
                }
            )

    topic_timeline_rows = [
        {"meeting_date": d, "topic": t, "count": c}
        for (d, t), c in sorted(topic_timeline.items(), key=lambda x: (x[0][0], x[0][1]))
    ]

    findings = {
        "top_topics": topic_counter.most_common(10),
        "top_people": person_counter.most_common(10),
        "cases_many_docs": case_doc_count.most_common(10),
        "cases_many_cross_refs": case_cross_refs.most_common(10),
        "risk_doc_count": len(risk_docs),
        "risk_docs": risk_docs[:30],
    }

    return pd.DataFrame(nodes), pd.DataFrame(edges), pd.DataFrame(topic_timeline_rows), findings


def write_findings(path: Path, findings: dict, llm_narrative: str = None):
    lines = [
        "# Investigation Findings",
        "",
    ]
    
    if llm_narrative:
        lines.extend([
            "## AI-Generated Narrative Analysis",
            "",
            llm_narrative,
            "",
        ])
    
    lines.extend([
        "## Top Topics",
    ])
    for topic, count in findings["top_topics"]:
        lines.append(f"- {topic}: {count}")

    lines.extend(["", "## Most Mentioned People"])
    for person, count in findings["top_people"]:
        lines.append(f"- {person}: {count}")

    lines.extend(["", "## Cases With Most Documents"])
    for case_id, count in findings["cases_many_docs"]:
        lines.append(f"- {case_id}: {count}")

    lines.extend(["", "## Cases With Most Cross References"])
    for case_id, count in findings["cases_many_cross_refs"]:
        lines.append(f"- {case_id}: {count}")

    lines.extend(["", f"## Risk-Signal Documents ({findings['risk_doc_count']})"])
    for row in findings["risk_docs"]:
        lines.append(f"- {row['meeting_date']} | {row['case_id']} | {row['document_title']} | {row['document_path']}")

    path.write_text("\n".join(lines), encoding="utf-8")


def generate_llm_narrative(findings: dict) -> str:
    """Generate AI narrative analysis of investigation findings using OpenAI."""
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    if not api_key:
        print("⚠️  OPENAI_API_KEY not set. Skipping LLM narrative generation.")
        return None
    
    client = OpenAI(api_key=api_key)
    
    # Build context for LLM
    top_topics = ", ".join([f"{t} ({c})" for t, c in findings["top_topics"][:5]])
    top_people = ", ".join([p for p, _ in findings["top_people"][:5]])
    risk_count = findings["risk_doc_count"]
    
    prompt = f"""Analyze the following Swedish regional government investigation data and provide a concise narrative summary of key findings:

Top Topics: {top_topics}
Most Mentioned People: {top_people}
Risk-Signal Documents: {risk_count}

Write a 2-3 paragraph executive summary in Swedish that explains:
1. What the main focus areas are (based on topics)
2. Key stakeholders involved
3. Risk signals or governance concerns
4. Recommended next steps for investigation

Keep it professional but accessible."""

    print(f"🤖 Generating LLM narrative with model: {model}")
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert analyst of Swedish regional government documents. Provide clear, actionable insights."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,
            max_tokens=800,
        )
        narrative = response.choices[0].message.content
        print("✅ LLM narrative generated successfully")
        return narrative
    except Exception as e:
        print(f"❌ LLM generation failed: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Build investigation graph and findings from ingested JSONL")
    parser.add_argument("--index", required=True, help="Path to JSONL index")
    parser.add_argument("--out-dir", default="data_out", help="Output folder for graph and findings")
    parser.add_argument("--llm", action="store_true", help="Generate LLM narrative (requires OPENAI_API_KEY)")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Start timing
    start_time = time.time()
    print("\n" + "="*60)
    print("🔍 REGIONAL GOVERNMENT INVESTIGATION AGENT")
    print("="*60)
    
    # Load records
    print("\n📂 Loading records...")
    load_start = time.time()
    records = load_records(Path(args.index))
    load_time = time.time() - load_start
    print(f"   ✅ Loaded {len(records)} documents in {load_time:.2f}s")
    
    # Build graph
    print("\n🔗 Building investigation graph...")
    graph_start = time.time()
    nodes_df, edges_df, timeline_df, findings = build_graph(records)
    graph_time = time.time() - graph_start
    print(f"   ✅ Graph built in {graph_time:.2f}s")
    print(f"      - {len(nodes_df)} nodes (documents, cases, topics, people)")
    print(f"      - {len(edges_df)} edges (relationships)")
    print(f"      - {len(timeline_df)} timeline entries")

    # Generate LLM narrative if requested
    llm_narrative = None
    if args.llm:
        llm_start = time.time()
        llm_narrative = generate_llm_narrative(findings)
        llm_time = time.time() - llm_start
        print(f"   ✅ LLM narrative generated in {llm_time:.2f}s")
    
    # Save outputs
    print("\n💾 Writing outputs...")
    output_start = time.time()
    nodes_df.to_csv(out_dir / "investigation_nodes.csv", index=False)
    edges_df.to_csv(out_dir / "investigation_edges.csv", index=False)
    timeline_df.to_csv(out_dir / "topic_timeline.csv", index=False)
    write_findings(out_dir / "investigation_findings.md", findings, llm_narrative)
    output_time = time.time() - output_start
    print(f"   ✅ Files written in {output_time:.2f}s")
    print(f"      - {out_dir / 'investigation_nodes.csv'}")
    print(f"      - {out_dir / 'investigation_edges.csv'}")
    print(f"      - {out_dir / 'topic_timeline.csv'}")
    print(f"      - {out_dir / 'investigation_findings.md'}")

    # Print findings summary
    print("\n📊 INVESTIGATION SUMMARY")
    print("-" * 60)
    print("Top Topics:")
    for topic, count in findings["top_topics"][:5]:
        print(f"   • {topic}: {count} mentions")
    
    print("\nMost Mentioned People:")
    for person, count in findings["top_people"][:5]:
        print(f"   • {person}: {count} mentions")
    
    print(f"\nRisk-Signal Documents: {findings['risk_doc_count']}")
    
    # Print timing summary
    total_time = time.time() - start_time
    print("\n⏱️  EXECUTION TIME SUMMARY")
    print("-" * 60)
    print(f"   Load:        {load_time:.2f}s")
    print(f"   Graph:       {graph_time:.2f}s")
    if args.llm:
        print(f"   LLM:         {llm_time:.2f}s")
    print(f"   Output:      {output_time:.2f}s")
    print(f"   TOTAL:       {total_time:.2f}s")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
