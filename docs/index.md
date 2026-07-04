---
hide:
  - navigation
  - toc
---

<div align="center" style="margin-top: 4rem; margin-bottom: 4rem;" markdown="1">

<h1 class="hero-text">Software that proves itself</h1>

<p class="hero-subtitle">
recurve turns a spec or a repo into falsifiable claims with executable probes,
then burns the gap between <em>claimed</em> and <em>proven</em> down to zero —
one fresh agent per cycle, behind a gate that never lies.
</p>

[Get Started](usage-provider-agnostic.md){ .md-button .md-button--primary }
&nbsp;&nbsp;
[Architecture](architecture.md){ .md-button }

</div>

## Install

```bash
git clone https://github.com/bordumb/recurve ~/tools/recurve
python3 -m pip install pyyaml
python3 ~/tools/recurve/recurve install        # → ~/.local/bin/recurve
```

!!! tip
    Prefer a shim, an alias, or a CI-friendly entrypoint? See the full
    [Installation guide](install.md). The engine is Python stdlib + PyYAML —
    it never fights your target's toolchain.

---

<div class="grid cards" markdown>

-   :material-clipboard-check-outline: **Claims, not vibes**

    ---

    Every promise becomes a **claim** with an executable **probe**: GREEN proven,
    RED not yet, BROKEN can't tell. If it can't be probed, it isn't a claim — so
    your README, your spec, and your intent all become machine-checkable.

-   :material-shield-check: **A gate that can't lie**

    ---

    Nothing closes on an agent's say-so. A claim goes green only when its probe
    passes *and* the fleet gate holds — and every probe keeps a **trap** it must
    fail against, so a weakened probe is caught mechanically.

-   :material-robot-outline: **Burn down unattended**

    ---

    Point it at a spec or a repo and walk away. One fresh agent per cycle takes
    the highest-value RED claim to GREEN, parks what it can't prove, reverts what
    regresses. The ledger is the only memory — **bring your own agent.**

</div>

---

## Quick tour

```bash
# 1 · turn a spec (or an existing repo) into a gated backlog of claims
recurve init --from-prd PRD.md --suite checkout

# 2 · record what's true today — GREEN promises become a regression suite
recurve baseline checkout

# 3 · burn red → green: from your agent session (the loop skill), or headless:
recurve run                       # agent defaults to a bypass-permissions Claude

# 4 · audit the checks themselves — every trap must still fail, measurably:
recurve drill --fuzz              # false-positive rate per probe, from generated known-bads
```

The primary way to run recurve is **inside your agent session**: invoke the
stamped `loop` skill and it drives gated cycles, one fresh sub-agent each.
Prefer to walk away? `recurve run` does the same headless. Either way the loop
believes the run-record and the gate, never the agent's word — that is the whole
point: **evidence, not belief.** ([ways to run](usage-provider-agnostic.md#step-3-kick-off-the-loop))

---

## Explore

<div class="grid cards" markdown>

-   :material-lightbulb-on-outline: **About**

    ---

    What recurve is, and the bet behind it.

    [The idea →](about.md)

-   :material-rocket-launch-outline: **Getting started**

    ---

    Initialize, design the claims, kick off the loop — and stop it safely.

    [Walk through it →](usage-provider-agnostic.md)

-   :material-shield-search: **Harden the checks**

    ---

    Who verifies the verifier? Traps re-proven, false positives measured,
    reference oracles compared.

    [Audit it →](hardening.md)

-   :material-database-outline: **Run data & trajectories**

    ---

    Every cycle is a record; the log exports as a dataset with reward
    provenance on every row.

    [Mine it →](run-data.md)

-   :material-source-branch: **Multi-repo & packs**

    ---

    Build one tree while sculpting another; distribute claims as installable packs.

    [Scale it →](multi-repo.md)

-   :material-sitemap-outline: **Architecture**

    ---

    The model, the verification layer, the evidence trail, and the engine.

    [How it works →](architecture.md)

</div>

[View on GitHub :material-github:](https://github.com/bordumb/recurve){ .md-button }
