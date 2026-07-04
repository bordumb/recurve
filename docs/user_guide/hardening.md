# Hardening your probes

The gate is only as trustworthy as the checks behind it — and checks fail
quietly, by testing less than you think they do. recurve's answer is a standing
discipline: **no probe certifies anything until it has been seen to fail**
(every claim ships a trap), plus an audit command that re-proves it — and, when
you opt in, *measures* it against generated counterexamples.

One rule governs everything on this page: **fix the probe, never the trap.**
When an audit fails, the check was wrong — weakening the evidence to quiet the
alarm is the one move the whole system exists to prevent.

## The drill — the standing audit

```bash
recurve drill
```

Every closed claim's probe is a regression guard forever. The drill re-runs each
guard against its kept counterexamples: every trap must still come back RED.

```text
  ● CFG-1/missing-key RED (still catches it)
  ⊘ EXT-2/corrupt-feed oracle-waived (external oracle absent, declared)
drill: 148 counterexample(s) audited across 145 guard(s), 0 waived, 1 oracle-waived
✓ drill clean — every audited guard still catches its defect.
```

Two kinds of debt are visible rather than silent:

- **Waived guards** — claims with `trap_waiver` (no fixture at all). Counted;
  the drill cannot repay what no fixture exercises.
- **Oracle-waived counterexamples** — a trap whose probe reports its *external
  oracle absent* (SKIP) on a claim that **declared** `oracle_waiver`. This
  mirrors the gate's own semantics: visible, non-blocking debt. An
  **undeclared** SKIP still fails the drill — a probe can never dodge the audit
  by claiming its oracle went missing.

A drill leaves no trace in the ledger or the run records: an audit that
polluted the dataset would poison the evidence it exists to validate.

## `--fuzz` — measured false positives

A curated trap is one question your probe is known to answer correctly — and a
probe can memorize one question. The fuzz pass asks a generated quiz: does the
probe reject known-bads it has *never seen*?

Ship a generator next to any probe worth the scrutiny:

```bash
#!/bin/sh
# probes/cfg-1.fuzz.sh — emit up to $FUZZ_N broken variants under $FUZZ_OUT,
# each shaped like a trap fixture (consumed via TRAP_FIXTURE).
i=0
for bad in '{}' '{"api_key": null}' '{"api_key": ""}' '{"api_key": 42}'; do
  [ "$i" -ge "$FUZZ_N" ] && break
  mkdir -p "$FUZZ_OUT/v$i"
  printf '%s' "$bad" > "$FUZZ_OUT/v$i/config.json"
  i=$((i+1))
done
```

```bash
recurve drill --fuzz
```

```text
  ● CFG-1 fuzz fpr 0/8          # rejected every generated known-bad
  ▲ API-3 fuzz fpr 3/8 — exceeds fuzz_fpr_max 0
fuzz: 2 fuzz-capable probe(s) measured, 3 false positive(s)
```

`fpr` is the probe's **false-positive rate** — the fraction of generated
known-bads it wrongly blessed. A leaky check is exposed as a number, before an
agent (or a bad day) finds the leak for you. Only claims that ship a
`<probe>.fuzz.sh` participate; everything else is untouched.

## `--iso` — verdict invariance

The fuzz pass checks that broken variants are *rejected*. Its dual: a probe's
verdict must **hold** on *semantics-preserving* variants of the true state. A
probe that flips when a config is reformatted, a field reordered, or a name
aliased has latched onto surface form, not meaning.

Ship an isomorphic generator (`probes/<id>.iso.sh`, env `ISO_OUT` / `ISO_N`)
that emits restatements of the state your probe checks. An iso-capable probe
reads `ISO_FIXTURE` when set and applies its normal acceptance check to that
variant:

```bash
recurve drill --iso
```

```text
  ● CFG-1 iso flips 0/8         # verdict held on every restatement
  ▲ LOG-2 iso flips 2/8 — exceeds iso_flip_max 0
iso: 2 iso-capable probe(s) measured, 2 flip(s)
```

A **flip** — any verdict other than the guard's true GREEN — fails the audit
past the threshold.

## `--diff` — reference oracles

Where a stricter or slower check of the same claim exists — a reference
implementation, an exhaustive validator — declare it on the claim:

```yaml
- id: CFG-1
  probe: probes/cfg-1.sh
  reference: probes/cfg-1.ref.sh
```

```bash
recurve drill --diff
```

The drill runs both against the same true state; **disagreement** (one GREEN,
the other RED) is an alarm that fails the audit and names both verdicts. Two
checks that agree by construction prove little — two *independent* checks that
agree prove a lot, and their disagreement is exactly the moment worth catching.

## Cost is a dial, not a policy

All three passes are **off by default** — a plain `recurve drill` is the same
audit it always was, and the gate never runs any of this. Budget knobs live in
`recurve.toml`:

```toml
[drill]
fuzz_n = 8          # variants per fuzz-capable probe
fuzz_fpr_max = 0.0  # failure threshold (0 = any false positive fails)
iso_n = 8           # variants per iso-capable probe
iso_flip_max = 0.0  # failure threshold (0 = any flip fails)
```

A sensible cadence: plain `drill` wherever you gate; `--fuzz --iso --diff` in
nightly CI or before a release. Write generators only for the probes that guard
something adversarial — parsers, validators, verifiers, anything whose job is
to say *no*. A leaky "no" is where trust dies quietly.
