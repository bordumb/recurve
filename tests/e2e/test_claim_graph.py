"""End-to-end coverage for the first-class claim graph (issue #24).

The claim graph is recurve's ledger read as a directed graph: nodes are gaps,
edges are the decomposition (`covers_claim`), curated logical dependency
(`depends_on`), and externally-ingested (`--edges`) relations. Everything here
is implementation-agnostic — the machinery touches only claim ids and edges,
never any proof system or test framework.

Test groups:
  1. model — `depends_on` / `group` parse (optional, defaulted, no schema break);
  2. graph build + JSON serialization to the documented schema;
  3. acyclicity (a `covers_claim`/`depends_on` cycle is rejected);
  4. external-edges ingestion (id-validated, `kind`-tagged, merged);
  5. graph-theory queries (critical-path, reachability/unlocks, frontier, metrics);
  6. CLI (`recurve export graph --json`, `--edges`, `--query`) and `validate` wiring.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from recurvelib.core.model import Gap, GapClass, GapParseError, Severity, Status


# --------------------------------------------------------------------------- #
# Group 1: model — the two new optional fields                                #
# --------------------------------------------------------------------------- #

def _parse(raw: dict) -> Gap:
    return Gap.parse(
        raw, suite="s", suite_dir=Path("/x"), source_file=Path("/x/gaps.yaml"),
        allowed_reads=("none",), default_reads="none",
    )


def _raw(**over) -> dict:
    base = dict(id="A", title="t", **{"class": "friction"}, status="open",
                severity="friction", reads="none", smallest_fix="do it",
                probe="probes/a.sh")
    base.update(over)
    return base


def test_depends_on_defaults_empty_no_schema_break():
    g = _parse(_raw())
    assert g.depends_on == ()
    assert g.group == ""


def test_depends_on_parses_id_list():
    g = _parse(_raw(depends_on=["B", "C"]))
    assert g.depends_on == ("B", "C")


def test_group_parses_opaque_string():
    g = _parse(_raw(group="phase-1"))
    assert g.group == "phase-1"


def test_depends_on_self_reference_rejected():
    with pytest.raises(GapParseError, match="depends_on"):
        _parse(_raw(depends_on=["A"]))


def test_depends_on_must_be_a_list():
    with pytest.raises(GapParseError, match="depends_on"):
        _parse(_raw(depends_on="B"))


def test_baseline_promotion_carries_group_and_depends_on():
    """gotcha 1: a draft that carries the new fields must survive the
    draft→ledger promotion (`_entry_yaml` KEY list), or the graph edges/group
    vanish the moment a claim is baselined."""
    from recurvelib.core.baseline import _entry_yaml
    entry = dict(id="A", title="t", **{"class": "friction"}, status="open",
                 severity="friction", reads="none", smallest_fix="do it",
                 probe="probes/a.sh", depends_on=["B"], group="phase-1")
    out = _entry_yaml(entry)
    assert "depends_on" in out
    assert "group" in out
    assert "phase-1" in out


# --------------------------------------------------------------------------- #
# Shared fixture helpers                                                       #
# --------------------------------------------------------------------------- #

def _gap(gid, *, suite="substrate", status="open", cls="missing-surface",
         severity="feature", covers_claim=(), depends_on=(), group="",
         has_probe=True):
    from recurvelib.core.model import Gap, GapClass, Severity, Status
    return Gap(
        id=gid, suite=suite, title=f"title {gid}", gap_class=GapClass(cls),
        status=Status(status), severity=Severity(severity), evidence=(),
        observed="", smallest_fix="x", unlocks="", reads="none", covers=(),
        probe=(Path(f"/x/probes/{gid}.sh") if has_probe else None),
        source_file=Path("/x/gaps.yaml"),
        covers_claim=tuple(covers_claim), depends_on=tuple(depends_on), group=group,
    )


def _ledger(*gaps):
    """Wrap gaps into a Ledger, grouping by suite in first-seen order."""
    from recurvelib.core.model import Ledger, SuiteLedger
    order: list[str] = []
    by_suite: dict[str, list] = {}
    for g in gaps:
        if g.suite not in by_suite:
            by_suite[g.suite] = []
            order.append(g.suite)
        by_suite[g.suite].append(g)
    return Ledger(suites=tuple(
        SuiteLedger(suite=s, suite_dir=Path("/x"), gaps=tuple(by_suite[s]))
        for s in order
    ))


# --------------------------------------------------------------------------- #
# Group 2: build the graph + serialize to the documented JSON schema          #
# --------------------------------------------------------------------------- #

def test_build_graph_nodes_carry_agnostic_fields():
    from recurvelib.analysis.graph import build_graph
    led = _ledger(
        _gap("SUB-BILIN", status="closed", severity="feature", group=None),
        _gap("SUB-HS-DERIV", covers_claim=["SUB-BILIN"]),
    )
    g = build_graph(led)
    n = g.node("SUB-BILIN")
    assert n is not None
    assert (n.id, n.suite, n.status, n.gap_class, n.severity) == (
        "SUB-BILIN", "substrate", "closed", "missing-surface", "feature")
    assert n.has_probe is True
    assert n.group is None


def test_serialized_json_matches_documented_schema():
    from recurvelib.analysis.graph import build_graph, to_json
    led = _ledger(
        _gap("SUB-BILIN", status="closed"),
        _gap("SUB-HS-DERIV", covers_claim=["SUB-BILIN"]),
        _gap("SUB-DUHAMEL", depends_on=["SUB-BILIN"]),
    )
    doc = to_json(build_graph(led))
    assert doc["generated_from"] == "ledger"
    assert doc["suites"] == ["substrate"]
    ids = [n["id"] for n in doc["nodes"]]
    assert ids == ["SUB-BILIN", "SUB-HS-DERIV", "SUB-DUHAMEL"]
    # node shape — exactly the documented keys, no implementation-named fields
    n0 = doc["nodes"][0]
    assert set(n0) == {"id", "suite", "title", "status", "class", "severity",
                       "group", "has_probe", "trap_count"}
    # edges: covers_claim is leaf→parent; depends_on is dependent→dependency
    edges = {(e["from"], e["to"], e["kind"]) for e in doc["edges"]}
    assert ("SUB-HS-DERIV", "SUB-BILIN", "covers_claim") in edges
    assert ("SUB-DUHAMEL", "SUB-BILIN", "depends_on") in edges
    assert len(doc["edges"]) == 2


def test_dangling_ledger_edge_dropped_from_graph():
    """A covers_claim/depends_on naming an id no gap has is tolerated (as the
    model already tolerates it in traversal) — it simply isn't emitted, so the
    graph never carries a dangling edge to a non-node."""
    from recurvelib.analysis.graph import build_graph, to_json
    led = _ledger(_gap("A", depends_on=["GHOST"], covers_claim=["PHANTOM"]))
    doc = to_json(build_graph(led))
    assert doc["edges"] == []


# --------------------------------------------------------------------------- #
# Group 3: acyclicity — the graph must be a DAG                               #
# --------------------------------------------------------------------------- #

def test_acyclic_graph_has_no_cycle():
    from recurvelib.analysis.graph import build_graph, find_cycle
    led = _ledger(
        _gap("A"),
        _gap("B", depends_on=["A"]),
        _gap("C", covers_claim=["B"]),
    )
    assert find_cycle(build_graph(led)) is None


def test_depends_on_cycle_detected():
    from recurvelib.analysis.graph import build_graph, find_cycle
    led = _ledger(_gap("A", depends_on=["B"]), _gap("B", depends_on=["A"]))
    cyc = find_cycle(build_graph(led))
    assert cyc is not None
    assert set(cyc) >= {"A", "B"}


def test_mixed_covers_and_depends_cycle_detected():
    """A cycle spanning both relations in prerequisite space must be caught:
    L is a leaf of P (P requires L) while L also depends_on P (L requires P)."""
    from recurvelib.analysis.graph import build_graph, find_cycle
    led = _ledger(_gap("P"), _gap("L", covers_claim=["P"], depends_on=["P"]))
    cyc = find_cycle(build_graph(led))
    assert cyc is not None
    assert set(cyc) >= {"P", "L"}


def test_self_loop_via_two_hops_detected():
    from recurvelib.analysis.graph import build_graph, find_cycle
    led = _ledger(
        _gap("A", depends_on=["B"]),
        _gap("B", depends_on=["C"]),
        _gap("C", depends_on=["A"]),
    )
    assert find_cycle(build_graph(led)) is not None


# --------------------------------------------------------------------------- #
# Group 4: external-edges ingestion (--edges)                                 #
# --------------------------------------------------------------------------- #

def test_ingest_merges_edge_tagged_ingested():
    from recurvelib.analysis.graph import build_graph, ingest_edges, to_json
    led = _ledger(_gap("A"), _gap("B"))
    edges = ingest_edges([{"from": "A", "to": "B"}], known_ids={"A", "B"})
    doc = to_json(build_graph(led, ingested=edges))
    assert {"from": "A", "to": "B", "kind": "ingested"} in doc["edges"]


def test_ingest_rejects_unknown_id():
    from recurvelib.analysis.graph import GraphError, ingest_edges
    with pytest.raises(GraphError, match="GHOST"):
        ingest_edges([{"from": "A", "to": "GHOST"}], known_ids={"A", "B"})


def test_ingest_preserves_provided_kind_as_provenance():
    from recurvelib.analysis.graph import build_graph, ingest_edges, to_json
    led = _ledger(_gap("A"), _gap("B"))
    edges = ingest_edges([{"from": "A", "to": "B", "kind": "proof_dep"}],
                         known_ids={"A", "B"})
    doc = to_json(build_graph(led, ingested=edges))
    e = [e for e in doc["edges"] if e["kind"] == "ingested"][0]
    assert e["source"] == "proof_dep"   # provided kind preserved, not lost


def test_ingest_passes_through_explicit_source():
    from recurvelib.analysis.graph import ingest_edges
    edges = ingest_edges([{"from": "A", "to": "B", "source": "lean-extractor"}],
                         known_ids={"A", "B"})
    assert edges[0].kind == "ingested"
    assert edges[0].provenance == "lean-extractor"


def test_ingest_rejects_malformed_row():
    from recurvelib.analysis.graph import GraphError, ingest_edges
    with pytest.raises(GraphError):
        ingest_edges([{"from": "A"}], known_ids={"A", "B"})  # missing 'to'


def test_ingested_edge_participates_in_requires_and_cycle():
    """An ingested dependency (dependent→dependency) is a real prerequisite:
    it can close the loop into a cycle just like depends_on."""
    from recurvelib.analysis.graph import build_graph, find_cycle, ingest_edges
    led = _ledger(_gap("A", depends_on=["B"]), _gap("B"))
    edges = ingest_edges([{"from": "B", "to": "A"}], known_ids={"A", "B"})
    assert find_cycle(build_graph(led, ingested=edges)) is not None


# --------------------------------------------------------------------------- #
# Group 5: graph-theory queries on the abstract graph                          #
# --------------------------------------------------------------------------- #
#
# Fixture graph (in prerequisite `requires` space):
#     A (apex, open)  requires {B, C}     — B, C are leaves of A (covers_claim)
#     B (open)        requires {D}         — via depends_on
#     C (open)        requires {}
#     D (base, closed) requires {}
#
def _query_fixture():
    from recurvelib.analysis.graph import build_graph
    led = _ledger(
        _gap("A", status="open"),
        _gap("B", status="open", covers_claim=["A"], depends_on=["D"]),
        _gap("C", status="open", covers_claim=["A"]),
        _gap("D", status="closed"),
    )
    return build_graph(led)


def test_critical_path_to_apex_is_longest_prerequisite_chain():
    from recurvelib.analysis.graph import critical_path
    assert critical_path(_query_fixture(), apex="A") == ["A", "B", "D"]


def test_critical_path_global_is_longest_path_anywhere():
    from recurvelib.analysis.graph import critical_path
    assert critical_path(_query_fixture()) == ["A", "B", "D"]


def test_reachability_unlocks_transitive_dependents():
    """Closing D unlocks everything that (transitively) requires it: B directly,
    A through B."""
    from recurvelib.analysis.graph import unlocks
    assert unlocks(_query_fixture(), "D") == ["A", "B"]


def test_reachability_apex_unlocks_nothing():
    from recurvelib.analysis.graph import unlocks
    assert unlocks(_query_fixture(), "A") == []


def test_frontier_is_open_nodes_with_all_prereqs_done():
    """B's only prereq (D) is closed, and C has no prereqs — both are workable
    now. A is blocked (B, C still open); D is already closed."""
    from recurvelib.analysis.graph import frontier
    assert frontier(_query_fixture()) == ["B", "C"]


def test_metrics_report_fanout_roots_and_leaves():
    from recurvelib.analysis.graph import metrics
    m = metrics(_query_fixture())
    assert m["node_count"] == 4
    assert m["edge_count"] == 3
    assert m["max_fanout"] == {"id": "A", "count": 2}
    assert m["roots"] == ["A"]        # apex: nothing requires it
    assert m["leaves"] == ["C", "D"]  # base: no prerequisites
    by_id = {n["id"]: n for n in m["nodes"]}
    assert by_id["A"]["requires"] == 2 and by_id["A"]["required_by"] == 0
    assert by_id["D"]["requires"] == 0 and by_id["D"]["required_by"] == 1


def test_critical_path_unknown_apex_rejected():
    from recurvelib.analysis.graph import GraphError, critical_path
    with pytest.raises(GraphError, match="NOPE"):
        critical_path(_query_fixture(), apex="NOPE")


# --------------------------------------------------------------------------- #
# Group 6: CLI — `recurve export graph` + `validate` acyclicity               #
# --------------------------------------------------------------------------- #

def _write_project(root: Path, gap_dicts: list[dict], traps: str = "off") -> Path:
    """Write a minimal on-disk recurve project (recurve.toml + one suite's
    gaps.yaml + a probe file per gap). Returns the recurve.toml path."""
    import yaml
    (root / "demo" / "probes").mkdir(parents=True, exist_ok=True)
    toml = (
        '[project]\nname = "t"\n\n'
        '[reads.none]\nmethod = "none"\n\n'
        f'[gate]\ntraps = "{traps}"\n\n'
        '[suites.demo]\ndir = "demo"\n'
    )
    (root / "recurve.toml").write_text(toml)
    for gd in gap_dicts:
        probe = gd.get("probe", f"probes/{gd['id']}.sh")
        (root / "demo" / probe).write_text("#!/usr/bin/env bash\nexit 1\n")
    (root / "demo" / "gaps.yaml").write_text(yaml.safe_dump(gap_dicts, sort_keys=False))
    return root / "recurve.toml"


def _gapdict(gid, **over):
    d = dict(id=gid, title=f"title {gid}", **{"class": "missing-surface"},
             status="open", severity="feature", reads="none",
             smallest_fix="x", probe=f"probes/{gid}.sh")
    d.update(over)
    return d


def _ns_export(toml, **kw):
    from types import SimpleNamespace
    base = dict(cmd="export", prog="recurve", config=str(toml), fmt="json",
                edges=None, query=None, node=None)
    base.update(kw)
    return SimpleNamespace(**base)


def test_cli_export_graph_json_matches_schema(tmp_path, capsys):
    from recurvelib.cli.commands.export import cmd_export
    toml = _write_project(tmp_path, [
        _gapdict("A", status="closed"),
        _gapdict("B", covers_claim=["A"]),
        _gapdict("C", depends_on=["A"], group="phase-1"),
    ])
    cmd_export(_ns_export(toml))
    doc = json.loads(capsys.readouterr().out)
    assert doc["generated_from"] == "ledger"
    assert doc["suites"] == ["demo"]
    assert {n["id"] for n in doc["nodes"]} == {"A", "B", "C"}
    assert {"from": "B", "to": "A", "kind": "covers_claim"} in doc["edges"]
    assert {"from": "C", "to": "A", "kind": "depends_on"} in doc["edges"]
    # opaque group passthrough survives to the wire
    assert next(n for n in doc["nodes"] if n["id"] == "C")["group"] == "phase-1"


def test_cli_export_edges_merges_and_validates(tmp_path, capsys):
    from recurvelib.cli.commands.export import cmd_export
    toml = _write_project(tmp_path, [_gapdict("A"), _gapdict("B")])
    edges_file = tmp_path / "edges.json"
    edges_file.write_text(json.dumps(
        [{"from": "A", "to": "B", "source": "lean-extractor"}]))
    cmd_export(_ns_export(toml, edges=str(edges_file)))
    doc = json.loads(capsys.readouterr().out)
    ing = [e for e in doc["edges"] if e["kind"] == "ingested"]
    assert ing == [{"from": "A", "to": "B", "kind": "ingested", "source": "lean-extractor"}]


def test_cli_export_edges_unknown_id_errors(tmp_path):
    from recurvelib.cli.commands.export import cmd_export
    toml = _write_project(tmp_path, [_gapdict("A"), _gapdict("B")])
    edges_file = tmp_path / "edges.json"
    edges_file.write_text(json.dumps([{"from": "A", "to": "GHOST"}]))
    with pytest.raises(SystemExit) as ei:
        cmd_export(_ns_export(toml, edges=str(edges_file)))
    assert ei.value.code != 0


def test_cli_export_query_frontier(tmp_path, capsys):
    from recurvelib.cli.commands.export import cmd_export
    toml = _write_project(tmp_path, [
        _gapdict("A", status="closed"),
        _gapdict("B", depends_on=["A"], status="open"),
        _gapdict("C", depends_on=["B"], status="open"),
    ])
    cmd_export(_ns_export(toml, query="frontier"))
    doc = json.loads(capsys.readouterr().out)
    assert doc["query"] == "frontier"
    assert doc["nodes"] == ["B"]   # A closed; B's prereq A done; C blocked by open B


def test_cli_export_query_reachability(tmp_path, capsys):
    from recurvelib.cli.commands.export import cmd_export
    toml = _write_project(tmp_path, [
        _gapdict("A", status="closed"),
        _gapdict("B", depends_on=["A"]),
        _gapdict("C", depends_on=["B"]),
    ])
    cmd_export(_ns_export(toml, query="reachability", node="A"))
    doc = json.loads(capsys.readouterr().out)
    assert doc["node"] == "A"
    assert doc["unlocks"] == ["B", "C"]


def test_cli_export_via_typer_app(tmp_path, capsys):
    """The command is actually registered on the Typer app (`recurve export
    graph --json`), not just callable as a function."""
    from recurvelib.cli.main import main
    toml = _write_project(tmp_path, [_gapdict("A")])
    # --config is a root option → it precedes the subcommand.
    with pytest.raises(SystemExit) as ei:
        main(argv=["--config", str(toml), "export", "graph", "--json"])
    assert ei.value.code == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["nodes"][0]["id"] == "A"


def test_validate_rejects_cyclic_ledger(tmp_path, capsys):
    from recurvelib.cli.commands.validate import cmd_validate
    from types import SimpleNamespace
    toml = _write_project(tmp_path, [
        _gapdict("A", depends_on=["B"]),
        _gapdict("B", depends_on=["A"]),
    ])
    with pytest.raises(SystemExit) as ei:
        cmd_validate(SimpleNamespace(cmd="validate", prog="recurve", config=str(toml)))
    assert ei.value.code == 1
    assert "cycle" in capsys.readouterr().out.lower()


def test_validate_accepts_acyclic_ledger(tmp_path, capsys):
    from recurvelib.cli.commands.validate import cmd_validate
    from types import SimpleNamespace
    # B requires A (depends_on) and A requires its leaf C (covers_claim) —
    # a real DAG A→C at the top, B→A on the spine, no cycle.
    toml = _write_project(tmp_path, [
        _gapdict("A"),
        _gapdict("B", depends_on=["A"]),
        _gapdict("C", covers_claim=["A"]),
    ])
    cmd_validate(SimpleNamespace(cmd="validate", prog="recurve", config=str(toml)))
    assert "cycle" not in capsys.readouterr().out.lower()
