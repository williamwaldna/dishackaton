import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd


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


def write_findings(path: Path, findings: dict):
    lines = [
        "# Investigation Findings",
        "",
        "## Top Topics",
    ]
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


def main():
    parser = argparse.ArgumentParser(description="Build investigation graph and findings from ingested JSONL")
    parser.add_argument("--index", required=True, help="Path to JSONL index")
    parser.add_argument("--out-dir", default="data_out", help="Output folder for graph and findings")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    records = load_records(Path(args.index))
    nodes_df, edges_df, timeline_df, findings = build_graph(records)

    nodes_df.to_csv(out_dir / "investigation_nodes.csv", index=False)
    edges_df.to_csv(out_dir / "investigation_edges.csv", index=False)
    timeline_df.to_csv(out_dir / "topic_timeline.csv", index=False)
    write_findings(out_dir / "investigation_findings.md", findings)

    print(f"Wrote nodes: {len(nodes_df)}")
    print(f"Wrote edges: {len(edges_df)}")
    print(f"Wrote timeline rows: {len(timeline_df)}")
    print(f"Wrote findings: {out_dir / 'investigation_findings.md'}")


if __name__ == "__main__":
    main()
