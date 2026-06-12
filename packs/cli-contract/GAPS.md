# cli-contract — the contract every well-behaved CLI keeps

> **Reader:** a human installing this pack. Set `PACK_CLI` to the command
> under test, skim the three claims, then baseline. Each probe carries a trap
> (a deliberately misbehaving CLI) proving it can fail.

## Conventions

- These map to `missing-surface` (the surface a CLI should have).
- Probes are parameterized by environment (`PACK_CLI`); they exit BROKEN, not
  RED, when unconfigured — absence of configuration is not a verdict.

## 1. --help prints usage and exits 0

Observable: `$PACK_CLI --help` exits 0 and the output contains a usage or
options section. Negative space: a help that exits nonzero or prints nothing
is RED.

## 2. an unknown flag is rejected: nonzero exit + error on stderr

Observable: `$PACK_CLI --definitely-not-a-real-flag-xyz` exits nonzero AND
writes an error to stderr. Negative space: a CLI that accepts anything
confirms nothing — silent acceptance is RED.

## 3. --version prints a dotted version and exits 0

Observable: `$PACK_CLI --version` exits 0 and prints `<digits>.<digits>`
somewhere. Negative space: "version unknown" is RED.
