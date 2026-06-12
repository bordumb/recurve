# Local-only acceptance fixtures

The Phase 0 acceptance (`diff.sh`) proves the engine live-equivalent to the
two working instances it was extracted from. Those instances live in the
origin workspace, not in this repository — so everything that points at or
captures them is **local-only and untracked**:

| Path | What it is |
| --- | --- |
| `ancestors.env` | where the original CLIs live (`ORIG_A_CLI`, `ORIG_B_CLI`) and their program names (`PROG_A`, `PROG_B`) |
| `configs/*.toml` | recurve configs that re-host each instance read-only |
| `golden/` | the frozen pre-migration output capture (historical record; the live diff superseded it) |
| `originals/` | pre-migration copies of the ancestor CLIs |

On a checkout without these (any clone of this repository), `diff.sh` exits
**3 — cannot compare**, and the self-host claim that wraps it (TK-2) reports
BROKEN: *absence of the oracle is never a verdict*. Every other self-host
claim, the engine selfcheck, the provenance probe, and the phase tests run
anywhere.

This split is the provenance-hygiene rule applied to the repository itself:
recurve ships nothing from its first customers — including their names.
