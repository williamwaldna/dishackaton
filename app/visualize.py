import argparse
import time
import webbrowser
from pathlib import Path

import networkx as nx
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def build_timeline_html(timeline_csv: Path, out_html: Path):
    timeline = pd.read_csv(timeline_csv)
    if timeline.empty:
        go.Figure().write_html(out_html)
        return

    timeline["meeting_date"] = pd.to_datetime(timeline["meeting_date"], errors="coerce")
    fig = px.line(
        timeline.sort_values("meeting_date"),
        x="meeting_date",
        y="count",
        color="topic",
        markers=True,
        title="Topic Timeline Across Meetings",
    )
    fig.update_layout(template="plotly_white")
    fig.write_html(out_html)


def build_graph_html(nodes_csv: Path, edges_csv: Path, out_html: Path, max_nodes: int = 120):
    nodes = pd.read_csv(nodes_csv)
    edges = pd.read_csv(edges_csv)

    if nodes.empty or edges.empty:
        go.Figure().write_html(out_html)
        return

    degree_counter = edges["source"].value_counts().add(edges["target"].value_counts(), fill_value=0)
    keep_ids = set(degree_counter.sort_values(ascending=False).head(max_nodes).index)

    nodes = nodes[nodes["id"].isin(keep_ids)].copy()
    edges = edges[edges["source"].isin(keep_ids) & edges["target"].isin(keep_ids)].copy()

    g = nx.Graph()
    for _, row in nodes.iterrows():
        g.add_node(row["id"], label=row.get("label", row["id"]), ntype=row.get("type", "node"))
    for _, row in edges.iterrows():
        g.add_edge(row["source"], row["target"], relation=row.get("relation", "link"))

    pos = nx.spring_layout(g, k=0.55, iterations=60, seed=42)

    edge_x, edge_y = [], []
    for src, tgt in g.edges():
        x0, y0 = pos[src]
        x1, y1 = pos[tgt]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])

    node_x, node_y, labels, colors = [], [], [], []
    color_map = {
        "document": "#4c78a8",
        "case": "#f58518",
        "topic": "#54a24b",
        "person": "#e45756",
    }

    for node_id, attrs in g.nodes(data=True):
        x, y = pos[node_id]
        node_x.append(x)
        node_y.append(y)
        labels.append(f"{attrs.get('label', node_id)} ({attrs.get('ntype', 'node')})")
        colors.append(color_map.get(attrs.get("ntype", "node"), "#72b7b2"))

    edge_trace = go.Scatter(
        x=edge_x,
        y=edge_y,
        line=dict(width=0.5, color="#888"),
        hoverinfo="none",
        mode="lines",
    )

    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        mode="markers",
        hoverinfo="text",
        text=labels,
        marker=dict(size=9, color=colors, line=dict(width=0.5, color="#333")),
    )

    fig = go.Figure(data=[edge_trace, node_trace])
    fig.update_layout(
        title="Investigation Link Graph (Top Connected Nodes)",
        showlegend=False,
        margin=dict(l=0, r=0, b=0, t=40),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        template="plotly_white",
    )
    fig.write_html(out_html)


def main():
    parser = argparse.ArgumentParser(description="Generate investigation visualizations")
    parser.add_argument("--out-dir", default="data_out", help="Directory with investigation CSV files")
    parser.add_argument("--no-open", action="store_true", help="Don't open visualizations in browser")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    
    print("\n" + "="*60)
    print("🎨 GENERATING VISUALIZATIONS")
    print("="*60)
    
    # Timeline
    print("\n📈 Generating timeline visualization...")
    timeline_start = time.time()
    build_timeline_html(out_dir / "topic_timeline.csv", out_dir / "timeline.html")
    timeline_time = time.time() - timeline_start
    print(f"   ✅ Timeline created in {timeline_time:.2f}s")
    print(f"      → {out_dir / 'timeline.html'}")
    
    # Graph
    print("\n🕸️  Generating network graph visualization...")
    graph_start = time.time()
    build_graph_html(out_dir / "investigation_nodes.csv", out_dir / "investigation_edges.csv", out_dir / "graph.html")
    graph_time = time.time() - graph_start
    print(f"   ✅ Graph created in {graph_time:.2f}s")
    print(f"      → {out_dir / 'graph.html'}")
    
    # Open in browser if requested
    if not args.no_open:
        print("\n🌐 Opening visualizations in browser...")
        timeline_file = (out_dir / "timeline.html").absolute()
        graph_file = (out_dir / "graph.html").absolute()
        
        try:
            webbrowser.open(f"file:///{timeline_file}")
            print(f"   ✅ Timeline opened: file:///{timeline_file}")
            time.sleep(1)  # Slight delay between opening
            webbrowser.open(f"file:///{graph_file}")
            print(f"   ✅ Graph opened: file:///{graph_file}")
        except Exception as e:
            print(f"   ❌ Failed to open browser: {e}")
            print(f"      Open manually: {timeline_file}")
            print(f"      Open manually: {graph_file}")
    
    print("\n" + "="*60)
    print("✨ Visualization complete!")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
