import json
import os
import sys
from collections import Counter
from pathlib import Path
from urllib import error, request

import pandas as pd
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.query import load_records, search

st.set_page_config(page_title="Region Agent Dashboard", layout="wide")


DEFAULT_OUT_DIR = BASE_DIR / "data_out"
DEFAULT_INDEX = DEFAULT_OUT_DIR / "2026-05-05-sample.jsonl"


def read_csv_safe(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def call_agent_api(base_url: str, question: str, top_k: int):
    payload = json.dumps({"question": question, "top_k": top_k}).encode("utf-8")
    req = request.Request(
        url=f"{base_url.rstrip('/')}/ask",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=20) as resp:
        body = resp.read().decode("utf-8")
        return json.loads(body)


def check_api_health(base_url: str):
    url = f"{base_url.rstrip('/')}/health"
    with request.urlopen(url, timeout=10) as resp:
        body = resp.read().decode("utf-8")
        return json.loads(body)


def local_query(index_path: Path, question: str, top_k: int):
    records = load_records(index_path)
    hits = search(records, question, top_k)
    summary = "\n".join(
        [
            f"- {h.get('meeting_date')} | {h.get('case_id')} | {h.get('document_type')} | {h.get('document_path')}"
            for h in hits
        ]
    )
    return {"answer": "Most relevant documents found:", "sources": hits, "summary": summary}


def _extract_risk_case_counts(findings_text: str) -> Counter:
    counts = Counter()
    marker = "## Risk-Signal Documents"
    if marker not in findings_text:
        return counts

    section = findings_text.split(marker, 1)[1]
    for raw in section.splitlines():
        line = raw.strip()
        if not line.startswith("-"):
            continue
        parts = [p.strip() for p in line[1:].split("|")]
        if len(parts) >= 2:
            case_id = parts[1]
            if case_id and case_id.lower() != "none":
                counts[case_id] += 1
    return counts


def _normalize_series(s: pd.Series) -> pd.Series:
    if s.empty:
        return s
    mn = float(s.min())
    mx = float(s.max())
    if mx <= mn:
        return pd.Series([0.0 for _ in range(len(s))], index=s.index)
    return (s - mn) / (mx - mn)


def build_semantic_case_insights(nodes_df: pd.DataFrame, edges_df: pd.DataFrame, findings_text: str) -> pd.DataFrame:
    if nodes_df.empty or edges_df.empty:
        return pd.DataFrame()

    docs = nodes_df[nodes_df["type"] == "document"].copy()
    if docs.empty:
        return pd.DataFrame()

    docs["case_id"] = docs["case_id"].fillna("unknown_case")
    doc_case = docs.set_index("id")["case_id"].to_dict()

    # Map document -> topic via edges and accumulate case topic fingerprints.
    topic_edges = edges_df[edges_df["relation"] == "mentions_topic"].copy()
    case_topics: dict[str, set[str]] = {}
    case_ai_mentions: Counter = Counter()
    case_budget_mentions: Counter = Counter()
    case_governance_mentions: Counter = Counter()

    for _, r in topic_edges.iterrows():
        src = r.get("source")
        tgt = str(r.get("target") or "")
        case = doc_case.get(src)
        if not case:
            continue
        topic = tgt.replace("topic:", "") if tgt.startswith("topic:") else tgt
        case_topics.setdefault(case, set()).add(topic)
        if topic == "ai":
            case_ai_mentions[case] += 1
        if topic == "budget":
            case_budget_mentions[case] += 1
        if topic == "governance":
            case_governance_mentions[case] += 1

    case_doc_count = docs.groupby("case_id").size().to_dict()

    # People mentions by case as proxy for actor complexity.
    people_edges = edges_df[edges_df["relation"] == "mentions_person"].copy()
    case_people_mentions: Counter = Counter()
    for _, r in people_edges.iterrows():
        src = r.get("source")
        case = doc_case.get(src)
        if case:
            case_people_mentions[case] += 1

    risk_counts = _extract_risk_case_counts(findings_text)

    # Cross-case similarity based on topic fingerprint overlap.
    case_cross_similarity: Counter = Counter()
    all_cases = sorted(set(list(case_doc_count.keys()) + list(case_topics.keys())))
    for i, a in enumerate(all_cases):
        ta = case_topics.get(a, set())
        for b in all_cases[i + 1 :]:
            tb = case_topics.get(b, set())
            union = ta | tb
            if not union:
                continue
            sim = len(ta & tb) / len(union)
            if sim >= 0.5:
                case_cross_similarity[a] += 1
                case_cross_similarity[b] += 1

    rows = []
    for case in all_cases:
        topics = case_topics.get(case, set())
        rows.append(
            {
                "case_id": case,
                "doc_count": int(case_doc_count.get(case, 0)),
                "risk_signal_docs": int(risk_counts.get(case, 0)),
                "topic_diversity": int(len(topics)),
                "ai_mentions": int(case_ai_mentions.get(case, 0)),
                "budget_mentions": int(case_budget_mentions.get(case, 0)),
                "governance_mentions": int(case_governance_mentions.get(case, 0)),
                "people_mentions": int(case_people_mentions.get(case, 0)),
                "cross_case_similarity_links": int(case_cross_similarity.get(case, 0)),
                "topic_fingerprint": ", ".join(sorted(topics)) if topics else "(none)",
            }
        )

    out = pd.DataFrame(rows)
    if out.empty:
        return out

    # Hidden-link confidence score from multiple weak signals.
    out["n_doc"] = _normalize_series(out["doc_count"]) 
    out["n_risk"] = _normalize_series(out["risk_signal_docs"]) 
    out["n_topic"] = _normalize_series(out["topic_diversity"]) 
    out["n_cross"] = _normalize_series(out["cross_case_similarity_links"]) 
    out["n_people"] = _normalize_series(out["people_mentions"]) 

    out["hidden_link_confidence"] = (
        0.30 * out["n_risk"]
        + 0.20 * out["n_doc"]
        + 0.20 * out["n_cross"]
        + 0.15 * out["n_topic"]
        + 0.15 * out["n_people"]
    )

    def cluster_label(row):
        tags = []
        if row["ai_mentions"] > 0:
            tags.append("ai")
        if row["budget_mentions"] > 0:
            tags.append("budget")
        if row["governance_mentions"] > 0:
            tags.append("governance")
        if row["risk_signal_docs"] > 0:
            tags.append("risk")
        return "+".join(tags) if tags else "general"

    out["cluster"] = out.apply(cluster_label, axis=1)
    out = out.sort_values(["hidden_link_confidence", "risk_signal_docs", "doc_count"], ascending=[False, False, False])
    return out


def interpret_semantic_heuristic(question: str, sources: list[dict]) -> str:
    if not sources:
        return "No evidence returned, so no semantic interpretation can be produced."

    all_text = "\n".join(
        [
            f"{s.get('document_path', '')}\n{s.get('snippet', '')}".lower()
            for s in sources
        ]
    )

    case_counter = Counter()
    for s in sources:
        case_id = s.get("case_id")
        if case_id and str(case_id).strip().lower() != "none":
            case_counter[str(case_id)] += 1

    theme_map = {
        "governance_accountability": ["styrning", "ansvar", "öppenhet", "governance", "accountability"],
        "cost_procurement": ["kostnad", "budget", "viten", "upphandling", "procurement", "overrun"],
        "healthcare_delivery": ["vård", "patient", "kö", "screening", "healthcare"],
        "ai_implementation": ["ai", "uppfölj", "resultat", "driftsättning", "model"],
    }

    theme_hits = {}
    for theme, terms in theme_map.items():
        theme_hits[theme] = sum(all_text.count(term) for term in terms)

    strongest_themes = [k for k, v in sorted(theme_hits.items(), key=lambda x: x[1], reverse=True) if v > 0][:3]
    top_cases = case_counter.most_common(3)

    lines = []
    lines.append("### Semantic Interpretation")
    lines.append(f"- Investigative question: {question}")

    if top_cases:
        lines.append("- Most repeated case IDs in evidence:")
        for case_id, count in top_cases:
            lines.append(f"  - {case_id} ({count} hits)")

    if strongest_themes:
        lines.append("- Dominant themes inferred from snippets:")
        for theme in strongest_themes:
            lines.append(f"  - {theme.replace('_', ' ')} (signal={theme_hits[theme]})")

    if theme_hits["ai_implementation"] > 0 and theme_hits["cost_procurement"] > 0:
        lines.append("- Hidden-link hypothesis: AI rollout appears tied to procurement and cost-control scrutiny.")
    if theme_hits["governance_accountability"] > 0 and theme_hits["cost_procurement"] > 0:
        lines.append("- Hidden-link hypothesis: financial pressure and governance-accountability concerns co-occur across retrieved documents.")

    lines.append("- Suggested follow-up questions:")
    lines.append("  - Which case IDs recur across both AI and procurement-related interpellations?")
    lines.append("  - Where are concrete KPI outcomes missing while budget impact is discussed?")
    lines.append("  - Which responsible roles are repeated in answers without closure metrics?")
    return "\n".join(lines)


def interpret_semantic_llm(question: str, sources: list[dict], model: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    evidence_lines = []
    for s in sources[:8]:
        snippet = (s.get("snippet") or "")[:260].replace("\n", " ")
        evidence_lines.append(
            f"case={s.get('case_id')} score={s.get('score')} type={s.get('document_type')} path={s.get('document_path')} snippet={snippet}"
        )

    prompt = (
        "You are an investigative analyst. Use only the provided evidence. "
        "Produce: (1) semantic interpretation, (2) likely hidden links, (3) confidence caveats, "
        "(4) three concrete follow-up investigative questions.\n\n"
        f"Question: {question}\n\nEvidence:\n" + "\n".join(evidence_lines)
    )

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "Be concise, structured, and evidence-grounded."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    return resp.choices[0].message.content or "No interpretation generated."


def main():
    st.title("Region Investigative Dashboard")
    st.caption("Interactive exploration of investigation outputs with live Q&A")

    with st.sidebar:
        st.header("Settings")
        out_dir = Path(st.text_input("Output directory", str(DEFAULT_OUT_DIR)))
        index_path = Path(st.text_input("Index file", str(DEFAULT_INDEX)))
        api_base = st.text_input("Agent API URL", "http://127.0.0.1:8000")
        top_k = st.slider("Top K sources", min_value=1, max_value=20, value=6)
        semantic_mode = st.radio(
            "Semantic interpretation",
            ["Heuristic", "OpenAI (if key set)"],
            index=0,
            help="Heuristic is local and free. OpenAI generates richer semantic interpretation from retrieved evidence.",
        )
        llm_model = st.text_input("OpenAI model", os.getenv("OPENAI_MODEL", "gpt-4o-mini"))

        mode = st.radio(
            "Question answering mode",
            ["Use running API", "Use local retrieval"],
            index=0,
            help="API mode uses app.server endpoint. Local mode calls TF-IDF search directly.",
        )

        if mode == "Use running API":
            try:
                health = check_api_health(api_base)
                st.success(f"API online ({health.get('records', 0)} records)")
            except Exception as ex:
                st.warning(f"API unavailable: {ex}")

    nodes_df = read_csv_safe(out_dir / "investigation_nodes.csv")
    edges_df = read_csv_safe(out_dir / "investigation_edges.csv")
    timeline_df = read_csv_safe(out_dir / "topic_timeline.csv")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Nodes", int(len(nodes_df)) if not nodes_df.empty else 0)
    c2.metric("Edges", int(len(edges_df)) if not edges_df.empty else 0)
    c3.metric("Timeline Rows", int(len(timeline_df)) if not timeline_df.empty else 0)
    c4.metric(
        "Cases",
        int(nodes_df[nodes_df["type"] == "case"].shape[0]) if not nodes_df.empty and "type" in nodes_df.columns else 0,
    )

    st.subheader("Ask Investigative Questions")
    default_q = "Show links between AI investments, procurement decisions, and accountability in Region Stockholm."
    question = st.text_area("Question", value=default_q, height=100)

    if st.button("Run Investigation Query", type="primary"):
        if not question.strip():
            st.warning("Please enter a question.")
        else:
            try:
                if mode == "Use running API":
                    result = call_agent_api(api_base, question, top_k)
                else:
                    if not index_path.exists():
                        st.error(f"Index file not found: {index_path}")
                        return
                    result = local_query(index_path, question, top_k)

                st.markdown(f"**Answer:** {result.get('answer', '')}")
                st.text_area("Summary", result.get("summary", ""), height=140)

                sources = pd.DataFrame(result.get("sources", []))
                if not sources.empty:
                    cols = [c for c in ["score", "meeting_date", "case_id", "document_type", "document_path", "snippet"] if c in sources.columns]
                    st.dataframe(sources[cols], width="stretch", height=320)

                    source_records = result.get("sources", [])
                    if semantic_mode == "OpenAI (if key set)":
                        try:
                            semantic_text = interpret_semantic_llm(question, source_records, llm_model)
                        except Exception as ex:
                            semantic_text = f"LLM interpretation failed: {ex}\n\nFalling back to heuristic interpretation.\n\n"
                            semantic_text += interpret_semantic_heuristic(question, source_records)
                    else:
                        semantic_text = interpret_semantic_heuristic(question, source_records)

                    st.markdown(semantic_text)

                    if "qa_history" not in st.session_state:
                        st.session_state["qa_history"] = []
                    st.session_state["qa_history"].append(
                        {
                            "question": question,
                            "summary": result.get("summary", ""),
                            "semantic": semantic_text,
                        }
                    )
                else:
                    st.info("No sources returned.")
            except error.HTTPError as ex:
                detail = ex.read().decode("utf-8", errors="ignore")
                st.error(f"API error ({ex.code}): {detail}")
            except Exception as ex:
                st.error(f"Failed to run query: {ex}")

    findings_path = out_dir / "investigation_findings.md"
    findings_text = findings_path.read_text(encoding="utf-8", errors="ignore") if findings_path.exists() else ""
    insights_df = build_semantic_case_insights(nodes_df, edges_df, findings_text)

    tab1, tab2, tab3, tab4 = st.tabs(["Findings", "Timeline", "Graph", "Semantic Insights"])

    if st.session_state.get("qa_history"):
        with st.expander("Question History", expanded=False):
            for i, item in enumerate(reversed(st.session_state["qa_history"][-6:]), start=1):
                st.markdown(f"**Q{i}:** {item['question']}")
                st.text_area(f"Summary {i}", item["summary"], height=110)
                st.markdown(item["semantic"])
                st.divider()

    with tab1:
        hidden_path = out_dir / "hidden_connections_analysis.md"
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("### Investigation Findings")
            if findings_path.exists():
                st.markdown(findings_path.read_text(encoding="utf-8", errors="ignore"))
            else:
                st.info(f"Missing file: {findings_path}")
        with col_b:
            st.markdown("### Hidden Connections")
            if hidden_path.exists():
                st.markdown(hidden_path.read_text(encoding="utf-8", errors="ignore"))
            else:
                st.info(f"Missing file: {hidden_path}")

    with tab2:
        timeline_html = out_dir / "timeline.html"
        st.markdown("### Interactive Topic Timeline")
        if timeline_html.exists():
            st.iframe(timeline_html.resolve().as_uri(), height=760)
        else:
            st.info(f"Missing file: {timeline_html}")

    with tab3:
        graph_html = out_dir / "graph.html"
        st.markdown("### Interactive Investigation Graph")
        if graph_html.exists():
            st.iframe(graph_html.resolve().as_uri(), height=760)
        else:
            st.info(f"Missing file: {graph_html}")

    with tab4:
        st.markdown("### Suspicious Case Clusters")
        st.caption("Auto-ranked using risk density, cross-case topic overlap, actor complexity, and document concentration.")
        if insights_df.empty:
            st.info("Not enough data to build semantic insights.")
        else:
            view_cols = [
                "case_id",
                "cluster",
                "hidden_link_confidence",
                "risk_signal_docs",
                "doc_count",
                "cross_case_similarity_links",
                "topic_diversity",
                "ai_mentions",
                "budget_mentions",
                "governance_mentions",
                "people_mentions",
                "topic_fingerprint",
            ]
            show_df = insights_df[view_cols].copy()
            show_df["hidden_link_confidence"] = show_df["hidden_link_confidence"].round(3)
            st.dataframe(show_df, width="stretch", height=430)

            st.markdown("### Top Hidden-Link Candidates")
            for _, r in insights_df.head(8).iterrows():
                st.markdown(
                    f"- **{r['case_id']}** | confidence={r['hidden_link_confidence']:.3f} | cluster={r['cluster']} | "
                    f"risk_docs={int(r['risk_signal_docs'])} | docs={int(r['doc_count'])} | topic_overlap_links={int(r['cross_case_similarity_links'])}"
                )


if __name__ == "__main__":
    main()
