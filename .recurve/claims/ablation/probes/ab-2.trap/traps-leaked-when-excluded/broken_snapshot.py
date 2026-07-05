# A broken build_claim_snapshot that never strips existing traps, even when
# include_existing_traps=False and trap_relpaths names them.
import dataclasses
import subprocess
import tempfile
from pathlib import Path


@dataclasses.dataclass(frozen=True)
class ClaimSnapshot:
    root: Path
    commit: str
    claim_id: str
    include_existing_traps: bool


def build_claim_snapshot(repo, ref, claim_id, *, include_existing_traps=False,
                         trap_relpaths=(), require_clean=True):
    rev = subprocess.run(["git", "-C", str(repo), "rev-parse", "--verify", f"{ref}^{{commit}}"],
                        capture_output=True, text=True)
    commit = rev.stdout.strip()
    dest = Path(tempfile.mkdtemp(prefix="broken-snap-"))
    proc = subprocess.run(["git", "-C", str(repo), "archive", commit], capture_output=True)
    subprocess.run(["tar", "-x", "-C", str(dest)], input=proc.stdout, capture_output=True)
    # BUG: trap_relpaths is accepted but never used — nothing is stripped.
    return ClaimSnapshot(root=dest, commit=commit, claim_id=claim_id,
                         include_existing_traps=include_existing_traps)
