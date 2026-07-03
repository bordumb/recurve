# Claim packs

A **claim pack** is claims as a distributable unit, the way packages are: a
versioned bundle of claim drafts, their probes, and their traps for a recurring
claim shape — a CLI contract, a performance SLO, an API conformance suite, a
compliance regime. Author a suite once, and anyone can install it and gate their
own project against it.

## The one rule: a pack never touches the ledger

Installing a pack drops **drafts**, never observations. A pack is *someone else's
intentions*; intentions become observations only by being measured **here**,
through the [baseline ceremony](usage-provider-agnostic.md#step-2-design). So a pack you install is
never trusted on the author's word — you re-run its probes on your own tree and
promote what actually holds. This is what makes packs safe to share: the receiver
always measures for itself.

## Export a suite

```bash
recurve pack export <suite> --out <path> [--version 0.1.0]
```

Bundles the suite's claims (demoted from ledger entries back to **drafts** —
unbaselined, because the receiving project must measure for itself), its probes,
its traps, and a `pack.toml` manifest. Choose the output form by extension:

```bash
recurve pack export cli --out ./cli-pack            # a pack directory
recurve pack export cli --out ./cli-pack.tgz        # a portable tarball
```

## Install a pack

```bash
recurve pack install <path> --suite <name>
```

Unpacks into `claims/<name>/` as `gaps.draft.yaml` + `probes/` (traps included)
and registers `[suites.<name>]` in your `recurve.toml`. It **refuses to overwrite**
a suite you already have — packs never clobber. Then the drafts walk the normal
door into your ledger:

```bash
recurve pack install ./cli-pack.tgz --suite cli
# review the drafts, set any PACK_* env/config the probes document, then:
recurve baseline cli          # measure them locally → the ceremony promotes
recurve matrix --gate         # the installed suite now gates your project
```

## The round-trip

The whole point is that a suite published in one project installs and gates in a
**different** project, carrying its adversarial traps intact:

```mermaid
flowchart LR
    A[project A<br/>authored suite] -- pack export --> P[(pack<br/>drafts + probes + traps)]
    P -- pack install --> B[project B<br/>drafts registered]
    B -- baseline --> L[project B ledger<br/>re-measured locally]
    L -- matrix --gate --> G[gated in B]
```

Because the traps travel with the pack, project B doesn't just re-run the checks —
it re-runs them against their known counterexamples, so a probe that can no longer
fail is caught in B exactly as it would be in A.

## The import guard

`recurve import` regenerates draft **stubs** from a suite's probes. To keep it
from silently overwriting a hand-authored draft (or one you installed from a
pack), `import` refuses when `gaps.draft.yaml` already exists unless you pass
`--force`:

```bash
recurve import cli            # refuses if claims/cli/gaps.draft.yaml exists
recurve import cli --force    # explicit overwrite
```

## Shipped packs

recurve ships a few starter packs under `packs/` (e.g. a CLI-contract pack, a
performance-SLO pack). Point `pack install` at one to seed a suite, then baseline
it against your own tree.
