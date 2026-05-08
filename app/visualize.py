import argparse
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
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    build_timeline_html(out_dir / "topic_timeline.csv", out_dir / "timeline.html")
    build_graph_html(out_dir / "investigation_nodes.csv", out_dir / "investigation_edges.csv", out_dir / "graph.html")

    print(f"Wrote visualization: {out_dir / 'timeline.html'}")
    print(f"Wrote visualization: {out_dir / 'graph.html'}")


if __name__ == "__main__":
    main()
