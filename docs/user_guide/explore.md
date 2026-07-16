# Exploring the unknown (`recurve explore`)

The gate has exactly one currency: **GREEN**. That is what makes closure
trustworthy — but it also means an agent driving recurve will always route
*around* a genuinely-open problem. It decomposes down to the already-provable,
closes those, correctly labels the hard remainder "not known," and parks. That
is not timidity; GREEN is the only thing it is rewarded for, and the unknown
space contains none of it.

`recurve explore` adds the **second gradient** — one that rewards walking *into*
the unknown — without ever loosening the honesty the gate exists to enforce. It
does this by **inverting the trap.**

## The inversion

A **trap** is a known-bad a probe must *reject*: seeing it go RED proves the
probe can fail, and that is what licenses trusting its GREEN. A trap is a bullet
the probe must dodge — it guards a claim you believe **true**.

A **falsifier** is the mirror image, fired at a **conjecture** you do *not* yet
know: a genuine attempt to construct a counterexample.

- If it **lands** — finds a counterexample — the conjecture is **FALSIFIED** and
  pruned. A dead lead is real information.
- If a battery of *potent* falsifiers all **miss**, the conjecture **SURVIVES** —
  a trustworthy lead, because it withstood real attempts to destroy it, not a
  model's optimism.

!!! warning "A survival is a lead, never a proof"
    Explore mode scores whether an open lead is *alive*, not whether it is
    *true*. Only a kernel/probe GREEN mints proof. A SURVIVING conjecture stays
    RED — it is a graded, honestly-labeled hypothesis worth a proof attempt.

## The one rule that keeps it honest

The same discipline as the gate, pointed the other way:

**No survival counts until the falsifier has demonstrably *killed* a decoy.**

A conjecture that "survives" only because nobody tried hard is worthless — the
exact failure mode recurve exists to kill. So every falsifier ships a
**calibration decoy**: a known-false variant it *must* refute. A probe is only
trusted once its trap has been seen RED; a survival is only trusted once its
falsifier has been seen to **KILL**. A battery with no calibrated falsifier is
`BROKEN`, never `SURVIVING`.

## Arming a conjecture

A claim becomes a conjecture by carrying a `falsifiers/` directory beside its
probe — the structural inverse of a probe's `.trap/` dir. No new claim class:

```text
probes/
  my-claim.sh                 # the probe — is it PROVEN? (RED until it is)
  my-claim.trap/…             # (optional) the closure-side trap
  my-claim.falsifiers/        # ← this makes it a conjecture
    ode-search/
      run.sh                  # exit 0 KILLED · 1 SURVIVED · other BROKEN
      kind                    # numeric | fuzz | symbolic | adversary | partial-proof
      decoy/                  # the known-false variant run.sh MUST kill
```

`run.sh` reads `RECURVE_FALSIFY_TARGET`: when set (to the `decoy/` path) it must
attack the decoy and **KILL** it; when unset it attacks the real conjecture.

```bash
#!/usr/bin/env bash
# exit 0 = KILLED (counterexample found) · 1 = SURVIVED · other = BROKEN
exec python3 "$(dirname "${BASH_SOURCE[0]}")/search.py"   # your kill-attempt
```

## Running it

```bash
recurve explore
```

For every conjecture it reports the survival gradient:

```text
PROMOTED — proven (probe kernel-clean GREEN); hand to the closure loop:
  ★ FOO-1              probe GREEN — no longer a conjecture

SURVIVING — live leads, ranked by strength (the exploration frontier):
  ○ R8-RATIO           survived 1 calibrated · strength 1 · 1×numeric (unsound-proxy only)

FALSIFIED — dead leads (a counterexample was found); prune:
  ✗ BAR-2              KILLED — R ran away from R0=0.05 …

BROKEN — batteries with no demonstrated teeth; fix before trusting a survival:
  ▲ BAZ-3              failed calibration: did not KILL its decoy

frontier: surviving 1 · falsified 0 · broken 1 · promoted 1
```

- **PROMOTED** — the probe is GREEN: the lead is *proven*. It leaves the survival
  axis and becomes an ordinary closed claim for the closure loop (the jackpot).
- **SURVIVING** — a live lead, ranked by `frontier_rank` (strength, then count).
  That ranking *is* the reward gradient.
- **FALSIFIED** — a calibrated falsifier found a counterexample. Prune it.
- **BROKEN** — the battery has no demonstrated teeth. `--strict` exits nonzero on
  any of these, so CI can gate on it — a lead nobody can trust is a defect,
  exactly as a probe without a trap is.

The `falsifiers/` directory is **invisible to the closure gate** — `matrix`,
`gate`, and `validate` ignore it. A conjecture is scored on two independent
axes: *proven?* (its probe) and *alive?* (its battery).

## Graded survival

Survival is evidence, never a single "safe" bit — its strength is graded by how
sound the oracle underneath the falsifier is (the same spectrum as the rest of
recurve):

| `kind` | what it is | a survival is… |
|---|---|---|
| `numeric` | simulate and measure | **weak** — unsound proxy, a hint |
| `fuzz` | random-instance counterexample search | medium |
| `symbolic` | symbolic sign / monotonicity check | medium |
| `adversary` | an agent constructing a counterexample | medium–strong |
| `partial-proof` | a kernel-checked restricted case | **strong** — bottoms out in the oracle |

A conjecture reports its whole **profile** (`count · strength · by-kind`), and
numeric survivals are marked *unsound-proxy* wherever they appear. To lift a lead
above a hint, arm it with more, and stronger, independent falsifiers.

## The actor stays yours

As with the closure loop, recurve is BYO-agent: the *actor* that proposes
conjectures and authors falsifiers is any agent you plug in. `recurve explore` is
the deterministic **spine** that scores it — it never proposes and never trusts
the proposer. The trust comes from the calibrated battery, never from the agent.
