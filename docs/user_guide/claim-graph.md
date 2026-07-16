# The claim graph

recurve's ledger **already is a directed graph**. `covers_claim` records "this
claim is a RED-first *leaf* of that parent" (the decomposition fan-outs), and
recurve traverses it internally to auto-discharge a parent once its leaves
close. `recurve export graph` makes that graph **first-class**: a data export a
renderer can depend on, a set of graph-theory queries, and an ingestion seam for
edges your project derives itself.

The point is **data-driven, not hand-authored**. A development tree you write by
hand drifts — the failure mode the harness exists to prevent. Regenerated from
the ledger, the graph can never lie.

## Implementation-agnostic by contract

recurve is agnostic to *what* a probe checks — its only contract with an
implementation is "a probe is an executable that returns GREEN/RED/BROKEN." The
graph machinery keeps that discipline: **it operates only on claim ids and
edges**. It never parses Lean, Coq, a test framework, or any implementation
source. Deriving proof-dependency edges from a particular proof system is the
*consuming project's* job — that project emits edges in the ingestion format
below, and recurve stays blind to the implementation.

## Two relations, three edge kinds

| Relation | Meaning | Where it comes from |
|---|---|---|
| **Decomposition** (`covers_claim`) | leaf → parent (a RED-first fan-out) | the ledger, already |
| **Logical dependency** (`depends_on`) | this claim's proof/impl *uses* that claim | the ledger (curated) |
| **Ingested** (`--edges`) | a dependency your extractor derived | supplied by any means |

`covers_claim` captures fan-outs, not the load-bearing spine — which is exactly
why the spine's edges are *supplied* to recurve (ingested), not *derived* by it.

Both `depends_on` and `group` are **optional and defaulted** — adding them breaks
no existing ledger.

```yaml
# gaps.yaml
- id: SUB-DUHAMEL
  title: Duhamel bound
  class: missing-surface
  status: open
  severity: feature
  probe: probes/sub-duhamel.sh
  depends_on: [SUB-BILIN, SUB-HEAT-CTS]   # this proof uses these claims
  group: substrate                        # opaque label; recurve never interprets it
```

> ⚠️ Use `group`, **not `tier`**. `tier` is the *derived* oracle strength and a
> gap that sets it is rejected — a claim must not self-report its strength.

## Export the graph

```bash
recurve export graph --json
```

Emits the public JSON contract to stdout:

```json
{
  "generated_from": "ledger",
  "suites": ["substrate", "shells"],
  "nodes": [
    {"id": "SUB-BILIN", "suite": "substrate", "title": "...", "status": "closed",
     "class": "missing-surface", "severity": "feature",
     "group": null, "has_probe": true, "trap_count": 1}
  ],
  "edges": [
    {"from": "SUB-HS-DERIV", "to": "SUB-BILIN", "kind": "covers_claim"},
    {"from": "SUB-DUHAMEL",  "to": "SUB-BILIN", "kind": "depends_on"},
    {"from": "SUB-DUHAMEL",  "to": "SUB-HEAT-CTS", "kind": "ingested", "source": "lean-extractor"}
  ]
}
```

`status` carries the real four-value status (`open`, `sculpting`, `closed`,
`permanent`). There are no implementation-named fields; `group` is an opaque
passthrough; `kind` distinguishes decomposition, curated logical, and ingested
edges.

## Ingest external edges

Your project's Lean/Coq/test extractor contributes the load-bearing spine by
emitting a JSON file of edges. recurve does not care how the file was produced.

```bash
recurve export graph --json --edges FILE.json
```

The file is a list of edge objects:

```json
[
  {"from": "SUB-DUHAMEL", "to": "SUB-HEAT-CTS", "kind": "proof_dep", "source": "lean-extractor"}
]
```

- `from`, `to` — **required**; both must be claim ids in the ledger. An unknown
  id is a hard error (so a stale extractor edge can't silently vanish).
- `kind` — optional; the output edge is tagged `kind: "ingested"` (the
  provenance marker renderers filter on). Any `kind` you provide is preserved.
- `source` — optional free-form provenance string, passed through verbatim. When
  you give no `source`, a provided `kind` is preserved there instead, so nothing
  your extractor supplied is ever lost.

A recommended conventional location is `.recurve/graph-edges.json`; pass it to
`--edges`. Ingesting a set of edges that would introduce a **cycle** is rejected
— the graph must stay a DAG.

## Graph-theory queries

All queries run on the abstract prerequisite relation (`X` requires `Y` ⇔ `Y`
must close before `X`), derived from all three edge kinds. None of them know
anything about what a claim checks.

```bash
recurve export graph --query frontier
recurve export graph --query critical-path [--node APEX]
recurve export graph --query reachability --node ID
recurve export graph --query metrics
```

| Query | Answers |
|---|---|
| `frontier` | **The true progress frontier** — open claims whose every prerequisite is already closed. Workable *now*: a sounder `recurve next` that respects the dependency spine. |
| `critical-path` | The longest prerequisite chain (to `--node` if given, else anywhere) — the schedule's real bottleneck, `[apex, …, base]`. |
| `reachability` | **What does closing `--node` unlock?** — every claim that transitively requires it. |
| `metrics` | Fan-out/complexity: per-claim prerequisite and dependent counts, the biggest fan-out crux, the apex roots and base leaves. |

Each query merges `--edges` too, so you can ask "what does closing X unlock?"
over the full spine your extractor supplied.

## Acyclicity

A `covers_claim`/`depends_on` cycle — a claim that must close before itself — can
never be discharged, and every query above assumes a DAG. `recurve validate`
rejects such a cycle, naming the offending chain.

## Non-goals (these belong to your project, not recurve)

- **Deriving proof-dependency edges from a proof system** (e.g. a Lean
  meta-program walking each theorem's declaration dependencies). Your project
  emits those edges in the ingestion format above; recurve stays blind to the
  implementation.
- Any **implementation-named field** (`lean_decl`, etc.). Associate a claim with
  an implementation artifact in your own sidecar metadata, not a recurve field.
- The **bespoke renderer** (a D3/Cytoscape page, styling, phase labels). The
  export is the contract; the visualization is yours.
