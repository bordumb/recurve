"""The claim graph — recurve's ledger read as a first-class directed graph.

recurve's ledger *already is* a directed graph. `covers_claim` records "this
claim is a RED-first leaf of that parent" (decomposition), and this module adds
`depends_on` (a curated logical/proof dependency) and an external-edge
ingestion seam so a project's own extractor can supply the load-bearing spine.

**Implementation-agnostic by construction.** Everything here operates only on
claim *ids* and *edges*. It never parses Lean, Coq, a test framework, or any
implementation source — deriving proof-dependency edges from a proof system is
the *consuming project's* job; those edges arrive already-derived through the
ingestion contract (`ingest_edges`). Nothing in this module imports from, or
knows about, `recurvelib.core.probe_cache` / `_PROJECT_ROOT` /
`transitive_project_modules` (the pre-existing Lean leak the issue forbids
extending).

## Edge kinds and the internal `requires` relation

Three edge *kinds* are serialized faithfully in `from`/`to` form (see the JSON
schema in `to_json`), but every graph-theory query runs on one normalized
*prerequisite* relation, `requires`: ``X`` requires ``Y`` ⇔ ``Y`` must close
before ``X`` can. The two ledger relations point in *opposite* prerequisite
directions, so the mapping is deliberate and locked by tests:

| kind          | JSON edge (`from`→`to`)     | `requires` contribution        |
|---------------|-----------------------------|--------------------------------|
| covers_claim  | leaf → parent               | parent requires leaf           |
| depends_on    | dependent → dependency      | dependent requires dependency  |
| ingested      | dependent → dependency      | dependent requires dependency  |

(A parent is auto-discharged once its leaves close — so the parent *requires*
its leaves; `Ledger.children_of` is the same traversal. A claim whose proof
uses another claim *requires* that claim. Ingested edges use the dependency
reading — the documented use is a project's proof-dependency spine.)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from recurvelib.core.model import Gap, Ledger

# Statuses that count as "done" for the progress frontier — a prerequisite in
# either of these no longer blocks a dependent. (`permanent` is a fact of the
# world; `closed` is fixed + guarded.) `open`/`sculpting` are not-yet-done.
_DONE = {"closed", "permanent"}

# Edge-kind serialization order — deterministic, and matches the schema example
# (decomposition, then curated logical deps, then externally-ingested deps).
_KIND_ORDER = {"covers_claim": 0, "depends_on": 1, "ingested": 2}


@dataclass(frozen=True)
class Node:
    """One claim, projected to exactly the agnostic fields a renderer needs."""

    id: str
    suite: str
    title: str
    status: str        # open | sculpting | closed | permanent
    gap_class: str     # serialized as "class"
    severity: str
    group: str | None  # opaque passthrough; None when ungrouped
    has_probe: bool
    trap_count: int


@dataclass(frozen=True)
class Edge:
    """A directed edge in `from`/`to` (serialization) form. `provenance` carries
    an ingested edge's free-form source (or its provided `kind`) so nothing an
    extractor supplied is lost; it is None for ledger-derived edges."""

    source: str        # "from"
    target: str        # "to"
    kind: str          # covers_claim | depends_on | ingested
    provenance: str | None = None


class GraphError(ValueError):
    """The claim graph is not a valid DAG, or an ingested edge is malformed."""


@dataclass(frozen=True)
class ClaimGraph:
    nodes: tuple[Node, ...]
    edges: tuple[Edge, ...]
    suites: tuple[str, ...]

    @property
    def ids(self) -> frozenset[str]:
        return frozenset(n.id for n in self.nodes)

    def node(self, node_id: str) -> Node | None:
        return next((n for n in self.nodes if n.id == node_id), None)

    def requires(self) -> dict[str, set[str]]:
        """id → set of prerequisite ids that must close before it. Every id is a
        key (nodes with no prerequisites map to an empty set)."""
        req: dict[str, set[str]] = {n.id: set() for n in self.nodes}
        known = self.ids
        for e in self.edges:
            if e.source not in known or e.target not in known:
                continue
            if e.kind == "covers_claim":
                # leaf(source) → parent(target): the PARENT requires the leaf.
                req[e.target].add(e.source)
            else:
                # depends_on / ingested: dependent(source) requires dependency(target).
                req[e.source].add(e.target)
        return req

    def dependents(self) -> dict[str, set[str]]:
        """Reverse of `requires`: id → set of ids that (directly) require it."""
        dep: dict[str, set[str]] = {n.id: set() for n in self.nodes}
        for who, prereqs in self.requires().items():
            for p in prereqs:
                dep[p].add(who)
        return dep


def _node_of(g: Gap) -> Node:
    return Node(
        id=g.id, suite=g.suite, title=g.title, status=g.status.value,
        gap_class=g.gap_class.value, severity=g.severity.value,
        group=(g.group or None), has_probe=g.probe is not None,
        trap_count=len(g.traps),
    )


def build_graph(ledger: Ledger, ingested: Iterable[Edge] = ()) -> ClaimGraph:
    """Project a `Ledger` (+ any already-validated ingested edges) into a graph.

    Ledger edges whose endpoint is not itself a node are dropped — the model
    already tolerates a stale `covers_claim`/`depends_on` id in traversal, so
    the graph mirrors that tolerance rather than emitting a dangling edge to a
    non-node. Ingested edges are validated for endpoint existence *before* they
    reach here (see `ingest_edges`)."""
    nodes = tuple(_node_of(g) for g in ledger.gaps)
    known = frozenset(n.id for n in nodes)
    edges: list[Edge] = []
    for g in ledger.gaps:
        for parent in g.covers_claim:
            if parent in known:
                edges.append(Edge(source=g.id, target=parent, kind="covers_claim"))
        for dep in g.depends_on:
            if dep in known:
                edges.append(Edge(source=g.id, target=dep, kind="depends_on"))
    edges.extend(ingested)
    edges.sort(key=lambda e: (_KIND_ORDER.get(e.kind, 9), e.source, e.target))
    suites = tuple(s.suite for s in ledger.suites)
    return ClaimGraph(nodes=nodes, edges=tuple(edges), suites=suites)


def ingest_edges(rows: Iterable[dict], known_ids: Iterable[str]) -> list[Edge]:
    """Validate + tag externally-supplied edges (the `--edges FILE.json`
    contract). recurve does not care how the file was produced — a project's
    Lean/Coq/test extractor targets this format and recurve stays blind to the
    implementation.

    Each row is ``{"from": id, "to": id, "kind"?: str, "source"?: str}``.
    Both ids must exist in the ledger (unknown id = error). The edge is tagged
    ``kind="ingested"`` — the provenance marker renderers filter on — and any
    provided ``source`` (or, absent that, the provided ``kind``) is preserved
    verbatim as `Edge.provenance`, so nothing an extractor supplied is lost.
    The dependency reading applies: ``from`` requires ``to``."""
    known = set(known_ids)
    out: list[Edge] = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            raise GraphError(f"--edges row {i}: not a mapping: {row!r}")
        frm = row.get("from")
        to = row.get("to")
        if not frm or not to:
            raise GraphError(f"--edges row {i}: needs both 'from' and 'to' (got {row!r})")
        frm, to = str(frm), str(to)
        for end in (frm, to):
            if end not in known:
                raise GraphError(
                    f"--edges row {i}: unknown id {end!r} — every ingested edge "
                    f"endpoint must be a claim in the ledger")
        provided = row.get("source") or row.get("kind")
        provenance = str(provided) if provided else None
        out.append(Edge(source=frm, target=to, kind="ingested", provenance=provenance))
    return out


def find_cycle(graph: ClaimGraph) -> list[str] | None:
    """Return one directed cycle in the `requires` (prerequisite) relation as a
    list of ids ``[n0, n1, ..., n0]``, or None if the graph is a DAG. A cycle
    is a genuine circular prerequisite — a claim that (transitively) must close
    before itself — regardless of whether its edges are covers_claim,
    depends_on, or ingested."""
    req = graph.requires()
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {nid: WHITE for nid in req}
    stack: list[str] = []

    def visit(node: str) -> list[str] | None:
        color[node] = GRAY
        stack.append(node)
        for nxt in sorted(req[node]):  # sorted → deterministic cycle report
            if color[nxt] == GRAY:
                # back-edge: the cycle is stack[i:] + the closing node
                i = stack.index(nxt)
                return stack[i:] + [nxt]
            if color[nxt] == WHITE:
                found = visit(nxt)
                if found is not None:
                    return found
        color[node] = BLACK
        stack.pop()
        return None

    for nid in sorted(req):
        if color[nid] == WHITE:
            found = visit(nid)
            if found is not None:
                return found
    return None


# --------------------------------------------------------------------------- #
# Graph-theory queries — all on the abstract `requires` relation, none knowing #
# anything about what a claim checks.                                          #
# --------------------------------------------------------------------------- #

def critical_path(graph: ClaimGraph, apex: str | None = None) -> list[str]:
    """The longest prerequisite chain — the sequence of claims that must close
    in order, the schedule's real bottleneck.

    With `apex`, the longest chain *from that claim down to a base prerequisite*
    (deepest work an apex hides). Without, the longest chain anywhere in the
    graph. Returns the ids in order ``[apex, …, base]``. Raises `GraphError`
    on an unknown apex or a cycle (run `find_cycle` first at the gate)."""
    req = graph.requires()
    if apex is not None and apex not in req:
        raise GraphError(f"critical_path: unknown claim id {apex!r}")
    if find_cycle(graph) is not None:
        raise GraphError("critical_path: graph has a cycle — not a DAG")

    memo: dict[str, list[str]] = {}

    def longest_from(node: str) -> list[str]:
        if node in memo:
            return memo[node]
        best: list[str] = []
        for prereq in req[node]:
            cand = longest_from(prereq)
            if len(cand) > len(best):
                best = cand
        memo[node] = [node] + best
        return memo[node]

    if apex is not None:
        return longest_from(apex)
    best_path: list[str] = []
    for nid in sorted(req):
        cand = longest_from(nid)
        # tie-break on the start id for determinism
        if len(cand) > len(best_path):
            best_path = cand
    return best_path


def unlocks(graph: ClaimGraph, node_id: str) -> list[str]:
    """Reachability: the set of claims that closing `node_id` unlocks — every
    claim that (transitively) requires it. Sorted ids; excludes `node_id`
    itself. Unknown id → `GraphError`."""
    dep = graph.dependents()
    if node_id not in dep:
        raise GraphError(f"unlocks: unknown claim id {node_id!r}")
    seen: set[str] = set()
    stack = list(dep[node_id])
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        stack.extend(dep[cur])
    return sorted(seen)


def frontier(graph: ClaimGraph) -> list[str]:
    """The true progress frontier — open claims whose every prerequisite is
    already done (closed/permanent). These are workable *now*: a sounder
    `recurve next` that respects the dependency spine, not just severity."""
    req = graph.requires()
    status = {n.id: n.status for n in graph.nodes}
    out = [
        nid for nid, prereqs in req.items()
        if status[nid] not in _DONE
        and all(status[p] in _DONE for p in prereqs)
    ]
    return sorted(out)


def metrics(graph: ClaimGraph) -> dict:
    """Fan-out / complexity metrics on the abstract graph: per-claim direct
    prerequisite count (`requires`) and dependent count (`required_by`), the
    biggest fan-out crux, the apex roots (nothing requires them), and the base
    leaves (no prerequisites)."""
    req = graph.requires()
    dep = graph.dependents()
    nodes = [
        {"id": nid, "requires": len(req[nid]), "required_by": len(dep[nid])}
        for nid in sorted(req)
    ]
    edge_count = sum(len(v) for v in req.values())
    max_id, max_count = "", -1
    for nid in sorted(req):
        if len(req[nid]) > max_count:
            max_id, max_count = nid, len(req[nid])
    return {
        "node_count": len(req),
        "edge_count": edge_count,
        "max_fanout": {"id": max_id, "count": max_count} if req else {"id": None, "count": 0},
        "roots": sorted(nid for nid in req if not dep[nid]),
        "leaves": sorted(nid for nid in req if not req[nid]),
        "nodes": nodes,
    }


def to_json(graph: ClaimGraph) -> dict:
    """Serialize to the public JSON contract renderers depend on. No
    implementation-named fields; `group` is an opaque passthrough; `kind`
    distinguishes decomposition, curated logical, and ingested edges."""
    def edge_obj(e: Edge) -> dict:
        obj = {"from": e.source, "to": e.target, "kind": e.kind}
        if e.provenance is not None:
            obj["source"] = e.provenance
        return obj

    return {
        "generated_from": "ledger",
        "suites": list(graph.suites),
        "nodes": [
            {"id": n.id, "suite": n.suite, "title": n.title, "status": n.status,
             "class": n.gap_class, "severity": n.severity, "group": n.group,
             "has_probe": n.has_probe, "trap_count": n.trap_count}
            for n in graph.nodes
        ],
        "edges": [edge_obj(e) for e in graph.edges],
    }
