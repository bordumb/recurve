"""`recurve export graph` — the claim graph as data.

A thin serializer over the existing `Ledger` (nodes = gaps; edges =
`covers_claim` + `depends_on` + any `--edges` ingested edges), plus the
graph-theory queries. This is the public contract a renderer depends on: a
project regenerates the graph from the ledger so a hand-authored development
tree can never drift.

Implementation-agnostic by construction — it reads only claim ids and edges
(never any proof system or test framework), and touches none of the
Lean-specific machinery (`_PROJECT_ROOT` / `transitive_project_modules`) the
issue forbids extending.
"""

from __future__ import annotations

from ..base import *  # shared recurvelib imports
from ..base import (
    _fail,
    _config,
    _load,
    _filter,
    _parse_point,
    _parse_goal,
    _draft_backlog,
)


def cmd_export(args):
    import json as _json
    from pathlib import Path
    from recurvelib.analysis import graph as G

    cfg = _config(args)
    ledger = _load(cfg)

    fmt = getattr(args, "fmt", "json") or "json"
    if fmt != "json":
        _fail(f"unsupported export format {fmt!r} — only 'json' is supported")

    # Merge any externally-supplied edges (deliverable 2). recurve never asks
    # how the file was produced; it only validates that every endpoint is a
    # claim in the ledger and tags the edges `ingested`.
    ingested = []
    edges_path = getattr(args, "edges", None)
    if edges_path:
        p = Path(edges_path)
        if not p.exists():
            _fail(f"--edges file not found: {edges_path}")
        try:
            rows = _json.loads(p.read_text())
        except (OSError, ValueError) as e:
            _fail(f"--edges {edges_path}: not valid JSON: {e}")
        if not isinstance(rows, list):
            _fail(f"--edges {edges_path}: top level must be a list of edge objects")
        try:
            ingested = G.ingest_edges(rows, known_ids=[g.id for g in ledger.gaps])
        except G.GraphError as e:
            _fail(f"\033[31m✗ edge ingestion failed:\033[0m {e}")

    graph = G.build_graph(ledger, ingested=ingested)

    # Ingesting a cycle is a contract violation — the graph must be a DAG.
    if ingested:
        cyc = G.find_cycle(graph)
        if cyc is not None:
            _fail(f"\033[31m✗ ingested edges introduce a cycle:\033[0m {' → '.join(cyc)}")

    query = getattr(args, "query", None)
    if not query:
        print(_json.dumps(G.to_json(graph), indent=2))
        return

    node = getattr(args, "node", None)
    try:
        if query == "frontier":
            out = {"query": "frontier", "nodes": G.frontier(graph)}
        elif query == "critical-path":
            out = {"query": "critical-path", "apex": node,
                   "path": G.critical_path(graph, apex=node)}
        elif query == "reachability":
            if not node:
                _fail("--query reachability needs --node ID (the claim to close)")
            out = {"query": "reachability", "node": node,
                   "unlocks": G.unlocks(graph, node)}
        elif query == "metrics":
            out = {"query": "metrics", **G.metrics(graph)}
        else:
            _fail(f"unknown --query {query!r} — one of: "
                  f"frontier | critical-path | reachability | metrics")
    except G.GraphError as e:
        _fail(f"\033[31m✗ query failed:\033[0m {e}")
    print(_json.dumps(out, indent=2))
