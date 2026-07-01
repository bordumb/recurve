# recurve

**Claims-driven recursive software improvement.** Point recurve at a target —
an existing repo or a PRD — and it converts intent into falsifiable claims
with executable probes, then burns down the gap between *claimed* and
*proven*: one fresh agent per cycle, ratcheting monotonically, parking what
it can't prove, and reserving for humans exactly the judgments machines
shouldn't make.

It also decides whether a goal is *gateable* before making any claims, surfaces
what no claim covers, checks the build didn't drift from intent, and decides
when to stop — the [verification layer](architecture.md#the-verification-layer).

```bash
recurve ledger      # every claim and its status — the red backlog is the honest one
recurve matrix      # run every probe: GREEN / RED / BROKEN / STALE, and the gate verdict
recurve next        # the highest-value gap to work on right now
```

## Where to go

| Page | What it answers |
| --- | --- |
| [About](about.md) | What this is, and the bet behind it |
| [Architecture](architecture.md) | The vocabulary, the loop, and the engine |
| [Installation](install.md) | Getting `recurve` onto your PATH |
| [How to Use](usage.md) | Initialize → design → kick off the loop — single- or multi-tree (and how to stop it) |

!!! tip "The one command to trust"
    `recurve matrix --gate` exits non-zero on any regression, broken probe,
    stale artifact, or a guard probe that blessed its own counterexample.
    Everything else — including this documentation — is commentary. A claim
    is closed when its probe is GREEN and the gate is green fleet-wide,
    never because someone believes it is.
