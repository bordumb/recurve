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

## From a spec to proof

**1 — Write the spec.** A short PRD of what the software must do (`PRD.md`) —
or skip it entirely and point recurve at an existing repo to mine the promises
your README and docs already make.

**2 — Turn intent into a gated backlog.**

```bash
recurve init --from-prd PRD.md --suite checkout --tree .
```

Every *must* becomes a falsifiable **claim** with an executable **probe** — plus
an adversarial twin for the negative space specs always omit. With no code yet,
every claim is RED. That's correct: **the burndown is the build.**

**3 — Record what's true, then burn the red down.**

```bash
recurve baseline checkout                      # GREEN promises → a regression suite; RED → your honest backlog
AGENT_CMD='…' bash .recurve/workflows/burndown.sh   # one fresh agent per cycle, gated, until green
```

Nothing closes on anyone's say-so — a claim goes green only when its probe is
GREEN *and* the gate holds fleet-wide. That's the whole point: **evidence, not
belief.**

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
