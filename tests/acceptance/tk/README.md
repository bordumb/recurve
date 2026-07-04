# acceptance/ — permanent harness, do not delete

These scripts look like one-off migration leftovers; they are not. This is
the engine's standing acceptance harness, and it has live consumers:

| File | What it does | Consumed by |
| --- | --- | --- |
| `provenance.sh` | proves nothing target-specific ships in the engine | `tk-1` probe; `docs/user_guide/install.md` verification step |
| `diff.sh` | live-equivalence diff against the pre-extraction ancestor instances | `tk-2` probe (`--fast`) |
| `selfcheck.py` | engine self-check | `tk-3` probe |
| `test_phases.py` | end-to-end behavior tests over temp projects | `docs/user_guide/install.md` verification step; characterization safety net during engine refactors |
| `run.py` | harness entry helper | the scripts above |

Deleting this folder breaks the `tk-1`/`tk-2`/`tk-3` probes (BROKEN → fleet
gate red, every loop halts on baseline) and the documented install
verification.

The only ephemeral things here are the **local-only, untracked fixtures**
`diff.sh` can consume (`ancestors.env`, `configs/`, `golden/`, `originals/`)
— see `LOCAL.md`. On a checkout without them, `diff.sh` exits `3 — cannot
compare` and `tk-2` reports SKIP under its `oracle_waiver`: absence of the
oracle is never a verdict. That is expected, not rot.
